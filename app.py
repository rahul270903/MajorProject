from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt

from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
from io import BytesIO
import os



app = Flask(__name__)
app.secret_key = 'zmdb'

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Set your MySQL password here
app.config['MYSQL_DB'] = 'cocoa'

mysql = MySQL(app)
bcrypt = Bcrypt(app)


model = load_model('model.keras')


# Define the uploads folder
UPLOAD_FOLDER="static/uploads"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER




@app.route('/')
def index():
    return render_template('index.html')  # Create an index.html file

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        
        # Validation
        if not name or not email or not password:
            flash('All fields are required.', 'warning')
            return redirect(url_for('register'))
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO farmers (name, email, password) VALUES (%s, %s, %s)", (name, email, hashed_password))
            mysql.connection.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Email already exists or an error occurred.', 'danger')
            print(f"Error: {e}")  # Log the error for debugging
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Validation
        if not email or not password:
            flash('Email and password are required.', 'warning')
            return redirect(url_for('login'))

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM farmers WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()
        print(user)

        if user and bcrypt.check_password_hash(user[2], password):  # user[3] is the hashed password field
            session['loggedin'] = True
            session['id'] = user[0]  # user[0] is the farmer ID
            session['name'] = user[3]  # user[1] is the farmer name
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        return render_template('admin/dashboard.html', name=session['name'])
    flash('You must log in first.', 'warning')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))



# Prediction function
def predict_image(file):
    img = image.load_img(file, target_size=(250, 250))  # Ensure the target size matches your model's input
    img = image.img_to_array(img)
    img = np.expand_dims(img, axis=0)
    img = img / 255.0
    prediction = model.predict(img)
    predicted_class_index = np.argmax(prediction)
    predicted_probability = np.max(prediction)
    
    return predicted_class_index, predicted_probability

@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    try:
        # Save the file temporarily
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Make prediction
        predicted_class_index, predicted_probability = predict_image(file_path)

        # Map the class index to class names and recommendations
        recommendations = {
            0: {
                "disease": "Black Pod Rot",
                "recommendation": [
                    "Remove and destroy infected pods to prevent spread.",
                    "Maintain proper drainage in plantations to reduce waterlogging.",
                    "Apply fungicides like copper-based fungicides regularly.",
                    "Prune trees to improve airflow and reduce humidity."
                ]
            },
            1: {
                "disease": "Healthy",
                "recommendation": [
                    "Continue regular maintenance and monitoring.",
                    "Use organic fertilizers to promote growth.",
                    "Ensure proper irrigation and sunlight exposure.",
                    "Monitor for early signs of diseases or pests."
                ]
            },
            2: {
                "disease": "Pod Borer",
                "recommendation": [
                    "Use pheromone traps to monitor and control pod borers.",
                    "Apply insecticides specifically targeted at borers.",
                    "Harvest pods promptly to avoid infestation.",
                    "Inspect and clean plantations regularly to remove eggs and larvae."
                ]
            }
        }

        # Fetch the disease and recommendations based on prediction
        disease_data = recommendations.get(predicted_class_index, {})
        result = disease_data.get("disease", "Unknown")
        recommendation = disease_data.get("recommendation", ["No recommendations available."])

        # Return JSON response
        return render_template('admin/dashboard.html',
            result= result,
            probability= float(predicted_probability),
            recommendation= recommendation,
            file="../"+file_path.replace("\\", "/")
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
