# Recipe Organizer Web Application
#### Video Demo:  <https://youtu.be/0WGguNEWKKs>

## Description
This project is a web application for managing recipes. Users can register, log in, browse a collection of recipes, and add their own custom recipes. The application allows for detailed recipe creation, including a title, description, instructions, images, and a dynamic number of ingredients. Users can also edit or delete their own recipes, and mark other recipes as favorites.

## Features
* **User Authentication:** Secure registration and login functionality.
* **Password Recovery with Tokens:** To recover a forgotten password, the system simulates sending a secure token to the user's email address, which is stored in the database. This allows the user to then create a new password.
* **Recipe Management:** Users can create, view, edit, and delete their own recipes.
* **Dynamic Ingredients:** The "add recipe" and "edit recipe" forms allow users to add an unlimited number of ingredients. This feature was added using JavaScript so users can dynamically add as many ingredients fields as they need.
* **Image Uploads:** Recipes can be accompanied by an image, which is resized and stored securely on the server. This was achieved using the Pillow library for Python.
* **Favorites System:** Users can add recipes to a personal favorites list for easy access.
* **Database Management:** The application uses an SQLite database to store all user, recipe, and ingredient information.

## How to Run the Project
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/juanrda12/recipe-organizer-portfolio.git
    ```
2.  **Navigate to the project directory:**
    ```bash
    cd recipe-organizer-portfolio
    ```
3.  **Install the required dependencies:**
    ```bash
    # (optional) Create venv
    python -m venv .venv

    # Activate the venv (choose ONLY one):
    # macOS / Linux:
    source .venv/bin/activate
    # Windows (PowerShell):
    .venv\Scripts\Activate.ps1
    # Windows (CMD):
    .venv\Scripts\activate.bat

    # Install dependencies
    python -m pip install -r requirements.txt
    ```
4. **Set up the environment variable:**
    - Create a .env file in the project root (you can start from .env.example).
    - Add your SECRET_KEY to this file.
    - Example .env file:
    ```bash
    FLASK_APP=app.py
    FLASK_DEBUG=1
    SECRET_KEY=random_secret_key>
    ```
5.  **Create the database:**
    ```bash
    python schema.py
    ```
6.  **Run the Flask application:**
    ```bash
    debug mode:
    python -m flask run

    other option:
    flask run
    ```
7.  **Access the application** at `http://127.0.0.1:5000` in your web browser.

## File Structure
* **`flask_session:`** Automatically created by the Flask-Session extension to store session data. Saves a separate file on your server's disk for each active user session.

* **`static/`:** This directory stores all static files. `styles.css` handles the look and feel of the web pages, while `uploads/` is where user-uploaded recipe images are saved. `static/script.js` contains the JavaScript code that gives the option to add as many ingredients fields as the user needs.

* **`templates/`:** This folder contains all the HTML templates for the application, such as `index.html`, `layout.html`, `add_recipe.html`, `login.html`, and `recipe_detail.html`, as well as others related to password recovery.

* **`app.py`:** This is the core of the application. It contains all the Flask routes and backend logic. This is where user authentication is handled, and where all interactions with the database (creating, reading, updating, and deleting recipes) take place. It also manages file uploads and image processing.

* **`recipes.db`:** This file is the SQLite database that stores all of the application's data, including user accounts, recipe details, ingredients, and categories.

* **`requirements.txt`:** This file lists the project's required Python dependencies, which can be installed by running pip install -r requirements.txt.

* **`schema.py`:** This script is responsible for creating and populating the SQLite database. It defines the tables for users, recipes, ingredients, and categories. It also pre-populates the database with ten default recipes to give users meal ideas when they first start using the app.


## Design Choices and Rationale
* **Using SQLite:** I chose to use SQLite for this project since it's the program we learned to use during the course, so I was already comfortable working with it. I also had to study and research a little bit more on the web about its use, which proved beneficial in improving and expanding my knowledge of SQLite3. Also since it's a file-based database, which means there's no need for a separate server, makes the project easy to run and distribute.

* **Database Schema:** The use of separate tables for `recipes`, `ingredients`, and `recipe_categories` follows a relational database design principle. This prevents data redundancy and makes the data easier to manage and query.

* **Dynamic Ingredients:** At the beginning of the project I developed a fixed number of ingredient fields for users to add on their recipes, but later on the project close to the end of it I decided to implement a dynamic system using JavaScript. This provides a better user experience by allowing users to add as many ingredients as they need without cluttering the form with empty fields.

* **Template Reuse:** A key design choice was to reuse the `add_recipe.html` template for both adding and editing recipes. This was achieved using a flag system: Python logic and Jinja2 conditionals determine whether the user is creating a new recipe or editing an existing one, and the template's content and form actions are adjusted accordingly. This approach minimizes code duplication and simplifies maintenance.

* **Image Processing:** When an image is uploaded, it is automatically cropped to a 4:3 aspect ratio and resized to 600x450 pixels. This ensures a consistent look across all recipe pages and optimizes file size for better performance. I also decided to add a list of several supported formats for uploading photos.

* **Token-Based Recovery:** To implement a secure password reset feature without a live email server, I designed a token-based system. When a user requests a password reset, a unique, cryptographically secure token is generated and stored in a separate password_reset_tokens table in the database.  This token is then printed to the terminal, simulating the email-sending process and providing a link for the user to follow.

* **Security Best Practices:** The password recovery functionality incorporates several security measures. The reset tokens are set to expire after five minutes, preventing old or leaked tokens from being used indefinitely. Additionally, after a successful password reset, the token is immediately deleted from the database, ensuring it can only be used once. The forgot_password route also provides a generic success message to prevent user enumeration, a security vulnerability that could allow an attacker to determine if an email address is registered.

* **Two-Step Validation:** The password reset process is split into two parts: a GET request to validate the token and a POST request to handle the new password submission. This ensures that the token is checked for validity and expiration before a user can even attempt to change their password and is re-validated before the final update, providing an extra layer of security against malicious attacks.

## Technologies Used

* **Python:** The core programming language.

* **Flask:** The micro-framework used to build the web application.

* **SQLite:** The database for storing all application data.

* **HTML, CSS, JavaScript:** Used for the frontend development.

* **Pillow:** The Python Image Library used for processing and resizing uploaded images.

* **Flask-Session:** A Flask extension used to store user sessions on the filesystem, managing authenticated user states.

* **Flask-Moment:** A Flask extension that handles formatting dates and times in templates, which is useful for displaying timestamps.

* **python-dotenv:** A library that loads environment variables from a .env file, allowing you to configure the application's settings outside of the source code.

## Acknowledgements
I used AI-based tools, specifically Gemini, as a helper to assist with tasks such as implementing the dynamic ingredients feature and structuring parts of the password recovery logic. The core design and overall implementation of the project remain my own work.

## Roadmap (If I convert it to a product)
- CSRF + rate limiting.
- Real emails for password resets.
- Pagination and advanced filters (times, per diems, etc.).
- Docker and deployment (Railway/Render/Fly.io).
- HEIC support (with pillow-heif) if needed.
