import os
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_session import Session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps  # Needed for the login_required decorator
from flask_moment import Moment
from PIL import Image
from datetime import datetime, timedelta  # For managing token expiration
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure application
app = Flask(__name__)
# Apply ProxyFix to correctly handle URLs when deployed behind a proxy (Codespaces)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1, x_proto=1, x_port=1)

# Initialize Flask-Moment
moment = Moment(app)

# SECRET_KEY from environment variable
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "backup_key")

# FLASK-SESSION
app.config["SESSION_PERMANENT"] = False  # Sessions expire when browser closes
app.config["SESSION_TYPE"] = "filesystem"  # Store sessions in files
# Initialize the Flask-Session extension
Session(app)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False  # poné True si corrés detrás de HTTPS
)

UPLOAD_FOLDER = 'static/uploads'
# Allowed image file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 Megabytes

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    # Check if there's a file extension and if it's in our ALLOWED_EXTENSIONS set
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# database path
DATABASE = 'recipes.db'


def get_db_connection():
    conn = sqlite3.connect(DATABASE, check_same_thread=False)
    # columns by name row['username']
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

# Decorator to ensure a user is logged in


def login_required(f):
    """
    Decorate routes to require login.
    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            flash("You must be logged in to access this page.", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


@app.route("/")
@login_required
def index():
    """Show list of recipes, with search and filter."""
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = session["user_id"]
    system_user_id = 1

    # Get filter parameters from request.args
    # .get("q", "") provides empty string if 'q' not present
    query = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)  # type=int converts to int or None
    owner_filter = request.args.get("owner_filter", "my_and_default")

    recipes = []

    # Base SQL query parts
    sql_query_parts = [
        """
        SELECT
            r.id, r.title, r.description, r.instructions, r.prep_time, r.cook_time,
            r.user_id, r.image_filename, u.username AS owner_username
        FROM recipes r
        JOIN users u ON r.user_id = u.id
        """
    ]
    sql_params = []

    # WHERE clauses for filtering
    where_clauses = []

    # Apply owner filter based on selection
    if owner_filter == 'my_recipes':
        where_clauses.append("r.user_id = ?")
        sql_params.append(user_id)
    elif owner_filter == 'default_recipes':
        where_clauses.append("r.user_id = ?")
        sql_params.append(system_user_id)
    elif owner_filter == 'my_and_default':
        where_clauses.append("(r.user_id = ? OR r.user_id = ?)")
        sql_params.extend([user_id, system_user_id])
    elif owner_filter == 'all_recipes':
        # show all recipes (subject to other filters)
        pass
    else:
        # Fallback to my_and_default if an unexpected owner_filter value is received
        flash("Invalid owner filter selected. Displaying 'My & Default Recipes'.", "warning")
        where_clauses.append("(r.user_id = ? OR r.user_id = ?)")
        sql_params.extend([user_id, system_user_id])
        owner_filter = 'my_and_default'  # Reset for template rendering

    # Add search query filter if present
    if query:
        # Use LIKE for partial matching. '%query%' matches anywhere in the string.
        # We search in title, description, and ingredient names.
        where_clauses.append("""
            (r.title LIKE ? OR r.description LIKE ? OR EXISTS (
                SELECT 1 FROM ingredients i WHERE i.recipe_id = r.id AND i.name LIKE ?
            ))
        """)
        # Add '%' for LIKE operator
        sql_params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])

    # Add category filter if present
    if category_id:
        # Check if the category_id actually exists
        valid_category = cursor.execute(
            "SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone()
        if valid_category:
            where_clauses.append("""
                EXISTS (
                    SELECT 1 FROM recipe_categories rc WHERE rc.recipe_id = r.id AND rc.category_id = ?
                )
            """)
            sql_params.append(category_id)
        else:
            flash("Invalid category selected.", "danger")
            category_id = None  # Reset invalid category_id for template rendering

    # Combine all WHERE clauses
    if where_clauses:
        sql_query_parts.append("WHERE " + " AND ".join(where_clauses))

    sql_query_parts.append("ORDER BY r.title ASC")

    final_sql_query = " ".join(sql_query_parts)

    # Execute the query
    recipes = cursor.execute(final_sql_query, sql_params).fetchall()

    # Get all categories for the filter dropdown
    all_categories = cursor.execute("SELECT id, name FROM categories ORDER BY name").fetchall()

    conn.close()

    # Pass all necessary data to the template
    return render_template(
        "index.html",
        recipes=recipes,
        query=query,  # Pass the search query back to pre-fill the search box
        all_categories=all_categories,  # dropdown
        selected_category_id=category_id,
        owner_filter=owner_filter,
        system_user_id=system_user_id
    )


@app.route("/my_recipes")
@login_required
def my_recipes():
    """Display a list of recipes created by the current user."""
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch only recipes created by the current user
    cursor.execute("""
        SELECT r.id, r.title, r.description, r.prep_time, r.cook_time,
               r.image_filename, r.user_id, u.username AS owner_username
        FROM recipes r
        JOIN users u ON r.user_id = u.id
        WHERE r.user_id = ?
        ORDER BY r.title
    """, (user_id,))

    my_owned_recipes = cursor.fetchall()
    conn.close()

    return render_template("my_recipes.html", recipes=my_owned_recipes, system_user_id=1)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        email = request.form.get("email")

        # 1. ALL non-database-dependent validations FIRST
        if not username:
            flash("Must provide username", "danger")
            return render_template("register.html")
        if not password:
            flash("Must provide password", "danger")
            return render_template("register.html")
        if not confirmation:
            flash("Must confirm password", "danger")
            return render_template("register.html")
        if password != confirmation:
            flash("Passwords do not match", "danger")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("register.html")
        if not email:
            flash("Must provide email", "danger")
            return render_template("register.html")

        # 2. If all basic validations pass, then connect to the database for unique checks
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 3. Perform database-dependent validations
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                flash("Username already exists", "danger")
                return render_template("register.html")

            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                flash("Email already registered", "danger")
                return render_template("register.html")

            # 4. If all validations (form and database) pass, proceed with registration
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, hash, email) VALUES (?, ?, ?)",
                           (username, hashed_password, email))
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.Error as e:
            conn.rollback()
            flash(f"An unexpected error occurred during registration: {e}", "danger")
            return render_template("register.html")
        finally:
            if conn:
                conn.close()

    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    if request.method == "POST":

        session.clear()

        username_or_email = request.form.get("username_or_email")
        password = request.form.get("password")

        if not username_or_email:
            flash("Must provide username or email", "danger")
            return render_template("login.html")
        if not password:
            flash("Must provide password", "danger")
            return render_template("login.html")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Query database for username or email
        cursor.execute("SELECT * FROM users WHERE username = ? OR email = ?",
                       (username_or_email, username_or_email))
        user = cursor.fetchone()
        conn.close()

        # Check if username exists and password is correct
        if user is None or not check_password_hash(user["hash"], password):
            flash("Invalid username/email and/or password", "danger")
            return render_template("login.html")

        # Remember which user has logged in
        session["user_id"] = user["id"]
        # Store username for display (e.g., "Hello, [username]!")
        session["username"] = user["username"]

        # Redirect user to home page
        flash(f"Welcome back, {user['username']}!", "success")
        return redirect(url_for("index"))

    else:  # GET request
        response = make_response(render_template("login.html"))
        # Add Cache-Control headers
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


@app.route("/logout")
def logout():
    """Log user out"""

    # --- Debug prints ---
    print(f"\n--- LOGOUT DEBUG  ---")
    print(f"Session user_id BEFORE removal: {session.get('user_id')}")
    print(f"Session username BEFORE removal: {session.get('username')}")
    # --- End Debug ---

    # Instead of session.clear(), explicitly delete user_id and username
    if "user_id" in session:
        del session["user_id"]
    if "username" in session:
        del session["username"]

    # --- Debug prints ---
    print(f"Session user_id AFTER removal: {session.get('user_id')}")
    print(f"Session username AFTER removal: {session.get('username')}")
    print(f"Flash message (logout) set.")
    # --- End Debug ---

    flash("You have been logged out.", "info")

    # Add Cache-Control headers
    response = make_response(redirect(url_for("login")))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/add_recipe", methods=["GET", "POST"])
@login_required
def add_recipe():
    """Allow user to add a new recipe."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        instructions = request.form.get("instructions")
        prep_time = request.form.get("prep_time")
        cook_time = request.form.get("cook_time")
        user_id = session["user_id"]
        selected_category_ids = request.form.getlist("categories")

        image_file = request.files.get('image')
        image_filename = None  # Default to no image in the database

        # Flag to track if the form should be re-rendered
        should_rerender = False

        # New list for dynamically-submitted ingredients
        ingredients_list = []
        i = 0
        while True:
            ingredient_name_key = f'ingredient_name_{i}'
            ingredient_qty_key = f'ingredient_qty_{i}'

            ingredient_name = request.form.get(ingredient_name_key)
            ingredient_qty = request.form.get(ingredient_qty_key)

            # Stop if we can't find a name key for this index, as it means we are out of ingredients
            if ingredient_name is None:
                break

            # Only add to the list if the name field is not empty
            if ingredient_name.strip() != "":
                ingredients_list.append({
                    'name': ingredient_name,
                    'quantity_unit': ingredient_qty if ingredient_qty else ''
                })

            i += 1

        # Handle image upload
        if image_file and image_file.filename != '':
            if allowed_file(image_file.filename):
                original_filename_secured = secure_filename(image_file.filename)
                unique_filename = str(uuid.uuid4()) + '.' + \
                    original_filename_secured.rsplit('.', 1)[1].lower()
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                image_file.save(filepath)

                try:
                    img = Image.open(filepath)
                    original_width, original_height = img.size
                    target_aspect = 4 / 3

                    if original_width / original_height > target_aspect:
                        new_width = int(original_height * target_aspect)
                        left = (original_width - new_width) / 2
                        top = 0
                        right = (original_width + new_width) / 2
                        bottom = original_height
                    else:
                        new_height = int(original_width / target_aspect)
                        left = 0
                        top = (original_height - new_height) / 2
                        right = original_width
                        bottom = (original_height + new_height) / 2

                    img = img.crop((left, top, right, bottom))
                    img = img.resize((600, 450), Image.Resampling.LANCZOS)
                    img.save(filepath)
                    image_filename = unique_filename
                except Exception as e:
                    print(f"Error processing image {filepath}: {e}")
                    flash("Error processing image. Please try another file.", "warning")
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    image_filename = None
                    should_rerender = True  # Set flag to re-render form
            else:
                flash("Invalid file type for image. Allowed: png, jpg, jpeg, gif.", "danger")
                should_rerender = True  # Set flag to re-render form

        # Input Validation
        if not should_rerender and (not title or not instructions):
            flash("Recipe title and instructions are required.", "danger")
            should_rerender = True

        if should_rerender:
            all_categories = cursor.execute(
                "SELECT id, name FROM categories ORDER BY name").fetchall()
            conn.close()
            return render_template("add_recipe.html",
                                   categories=all_categories,
                                   title=title, description=description, instructions=instructions,
                                   prep_time=prep_time, cook_time=cook_time,
                                   selected_category_ids=selected_category_ids,
                                   ingredients=ingredients_list)  # Pass the dynamic list

        try:
            # Insert new recipe into recipes table
            cursor.execute(
                """
                INSERT INTO recipes (title, description, instructions, prep_time, cook_time, user_id, image_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (title, description, instructions, prep_time, cook_time, user_id, image_filename)
            )
            recipe_id = cursor.lastrowid  # Get the ID of the newly inserted recipe

            # Insert ingredients (loop dynamically) iterates over the same dynamic list created above
            for ingredient in ingredients_list:
                if ingredient['name']:
                    cursor.execute(
                        "INSERT INTO ingredients (recipe_id, name, quantity_unit) VALUES (?, ?, ?)",
                        (recipe_id, ingredient['name'], ingredient['quantity_unit'])
                    )

            # Insert selected categories into recipe_categories table
            if selected_category_ids:
                for category_id in selected_category_ids:
                    if cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone():
                        cursor.execute(
                            "INSERT INTO recipe_categories (recipe_id, category_id) VALUES (?, ?)",
                            (recipe_id, category_id)
                        )
                    else:
                        flash(
                            f"Invalid category ID '{category_id}' was selected and ignored.", "warning")

            conn.commit()
            flash("Recipe added successfully!", "success")
            return redirect(url_for("recipe_detail", recipe_id=recipe_id))

        except sqlite3.Error as e:
            conn.rollback()
            flash(f"An error occurred: {e}", "danger")
            print(f"Database error during add_recipe: {e}")
            all_categories = cursor.execute(
                "SELECT id, name FROM categories ORDER BY name").fetchall()
            conn.close()
            return render_template("add_recipe.html",
                                   categories=all_categories,
                                   title=title, description=description, instructions=instructions,
                                   prep_time=prep_time, cook_time=cook_time,
                                   selected_category_ids=selected_category_ids,
                                   ingredients=ingredients_list)
        finally:
            if conn:
                conn.close()

    else:  # GET request
        all_categories = cursor.execute("SELECT id, name FROM categories ORDER BY name").fetchall()
        conn.close()
        # pass a list with ONE empty dictionary, which the dynamic form will use to show one ingredient row.
        return render_template("add_recipe.html",
                               categories=all_categories,
                               ingredients=[{'name': '', 'quantity_unit': ''}])


@app.route("/recipe/<int:recipe_id>")
@login_required
def recipe_detail(recipe_id):
    """Display full details of a specific recipe."""
    conn = get_db_connection()
    cursor = conn.cursor()

    system_user_id = 1

    recipe = cursor.execute(
        """
        SELECT r.id, r.title, r.description, r.instructions, r.prep_time, r.cook_time,
               r.user_id, r.image_filename, u.username AS owner_username
        FROM recipes r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
        """,
        (recipe_id,)
    ).fetchone()

    if recipe is None:
        flash("Recipe not found.", "danger")
        conn.close()
        return redirect(url_for("index"))

    recipe = dict(recipe)  # Convert to mutable dictionary

    # Fetch ingredients for this recipe and ATTACH THEM TO THE RECIPE DICTIONARY
    ingredients_list = cursor.execute(
        "SELECT name, quantity_unit FROM ingredients WHERE recipe_id = ?",
        (recipe_id,)
    ).fetchall()
    recipe['ingredients'] = ingredients_list

    # same for categories
    categories_list = cursor.execute(
        """
        SELECT c.id, c.name
        FROM recipe_categories rc
        JOIN categories c ON rc.category_id = c.id
        WHERE rc.recipe_id = ?
        ORDER BY c.name
        """,
        (recipe_id,)
    ).fetchall()
    recipe['categories'] = categories_list

    user_id = session.get("user_id")

    is_favorited = False
    if user_id:  # Only check if a user is logged in
        cursor.execute("SELECT 1 FROM favorites WHERE user_id = ? AND recipe_id = ?",
                       (user_id, recipe_id))
        if cursor.fetchone():  # If a row is returned, it means it's favorited
            is_favorited = True

    conn.close()

    # 'recipe' dictionary contains ingredients and categories
    return render_template("recipe_detail.html",
                           recipe=recipe,
                           is_favorited=is_favorited,
                           system_user_id=system_user_id)


@app.route("/edit_recipe/<int:recipe_id>", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    """Allow user to edit an existing recipe."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch the recipe by ID
    recipe = cursor.execute(
        """
        SELECT r.id, r.title, r.description, r.instructions, r.prep_time, r.cook_time,
               r.user_id, r.image_filename, u.username AS owner_username
        FROM recipes r
        JOIN users u ON r.user_id = u.id
        WHERE r.id = ?
        """,
        (recipe_id,)
    ).fetchone()

    # Check if recipe exists and if the current user owns it
    if recipe is None or recipe["user_id"] != session["user_id"]:
        flash("Recipe not found or you don't have permission to edit it.", "danger")
        conn.close()
        return redirect(url_for("index"))

    # Convert to mutable dictionary here, same as before above in recipe_detail.
    recipe = dict(recipe)

    if request.method == "POST":
        # Get updated form data
        title = request.form.get("title")
        description = request.form.get("description")
        instructions = request.form.get("instructions")
        prep_time = request.form.get("prep_time")
        cook_time = request.form.get("cook_time")
        selected_category_ids = request.form.getlist("categories")

        # --- LOGIC FOR IMAGE HANDLING ---
        image_file = request.files.get('image')
        # Get checkbox value name="delete_current_image">
        delete_current_image = request.form.get('delete_current_image')
        image_filename_to_db = recipe['image_filename']  # Start with existing filename

        # Scenario 1: User explicitly wants to delete the current image
        if delete_current_image:
            if recipe['image_filename']:  # If there's an existing file to delete
                old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], recipe['image_filename'])
                if os.path.exists(old_filepath):
                    try:
                        os.remove(old_filepath)  # Delete the file from the filesystem
                        # For debugging
                        print(f"Successfully deleted old image file: {old_filepath}")
                    except OSError as e:
                        print(f"Error deleting old image file {old_filepath}: {e}")
                        flash(f"Error deleting old image: {e}", "warning")
                else:
                    # For debugging
                    print(
                        f"Warning: Old image file not found at {old_filepath} (was expected for deletion).")
            image_filename_to_db = None  # Set filename to NULL in DB

        # Scenario 2: User uploads a new image (only process if no explicit delete OR if a new file is provided)
        # This prioritizes explicit deletion if both are somehow triggered.
        if image_file and image_file.filename != '':
            if allowed_file(image_file.filename):
                # If a new file is uploaded, remove the old one first IF it hasn't already been marked for deletion
                # (for example: delete_current_image was not checked, or was checked but filename was None)
                if recipe['image_filename'] and not delete_current_image:
                    old_filepath = os.path.join(
                        app.config['UPLOAD_FOLDER'], recipe['image_filename'])
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                            print(
                                f"Successfully removed old image to replace with new: {old_filepath}")
                        except OSError as e:
                            print(f"Error removing old image for replacement {old_filepath}: {e}")
                            flash(f"Error replacing old image: {e}", "warning")

                original_filename_secured = secure_filename(image_file.filename)
                unique_filename = str(uuid.uuid4()) + '.' + \
                    original_filename_secured.rsplit('.', 1)[1].lower()
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                image_file.save(filepath)  # Save the uploaded file initially

                # --- IMAGE RESIZING LOGIC (SAME AS ADD_RECIPE) ---
                try:
                    img = Image.open(filepath)
                    original_width, original_height = img.size
                    target_aspect = 4 / 3

                    # Calculate new dimensions to fit 4:3 and crop from center
                    if original_width / original_height > target_aspect:
                        # Image is wider than 4:3, crop width
                        new_width = int(original_height * target_aspect)
                        left = (original_width - new_width) / 2
                        top = 0
                        right = (original_width + new_width) / 2
                        bottom = original_height
                    else:
                        # Image is taller than 4:3, crop height
                        new_height = int(original_width / target_aspect)
                        left = 0
                        top = (original_height - new_height) / 2
                        right = original_width
                        bottom = (original_height + new_height) / 2

                    # Crop the image to the 4:3 aspect ratio
                    img = img.crop((left, top, right, bottom))

                    # Resize to target dimensions (600x450)
                    img = img.resize((600, 450), Image.Resampling.LANCZOS)

                    # Save the processed image, overwriting the original uploaded file
                    img.save(filepath)
                    # For debugging
                    print(f"Image processed and saved at 600x450 (4:3): {filepath}")
                    image_filename_to_db = unique_filename  # Only set filename if processing successful
                except Exception as e:
                    print(f"Error processing image {filepath}: {e}")
                    flash("Error processing image. Please try another file.", "warning")
                    # Delete the uploaded file if processing failed
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    image_filename_to_db = None
                # --- END IMAGE RESIZING LOGIC ---
            else:
                flash("Invalid file type for image. Allowed: png, jpg, jpeg, gif.", "danger")
                # Re-fetch data for rendering the form with error message
                ingredients_on_error = cursor.execute(
                    "SELECT name, quantity_unit FROM ingredients WHERE recipe_id = ?", (recipe_id,)).fetchall()
                all_categories = cursor.execute(
                    "SELECT id, name FROM categories ORDER BY name").fetchall()
                selected_categories_current = cursor.execute(
                    "SELECT category_id FROM recipe_categories WHERE recipe_id = ?", (recipe_id,)).fetchall()
                selected_category_ids_current = [str(cat["category_id"])
                                                 for cat in selected_categories_current]
                conn.close()
                recipe['ingredients'] = ingredients_on_error  # Attach for template re-rendering
                return render_template("add_recipe.html",
                                       recipe=recipe,
                                       categories=all_categories,
                                       selected_category_ids=selected_category_ids_current,
                                       editing=True)
        # --- END LOGIC FOR IMAGE HANDLING ---

        # Input Validation (basic)
        if not title or not instructions:
            flash("Recipe title and instructions are required.", "danger")
            all_categories = cursor.execute(
                "SELECT id, name FROM categories ORDER BY name").fetchall()
            selected_categories_current = cursor.execute(
                "SELECT category_id FROM recipe_categories WHERE recipe_id = ?", (recipe_id,)).fetchall()
            selected_category_ids_current = [str(cat["category_id"])
                                             for cat in selected_categories_current]

            # --- INGREDIENT LOOP ---
            ingredients_list = []
            i = 0
            while True:
                ingredient_name_key = f'ingredient_name_{i}'
                ingredient_qty_key = f'ingredient_qty_{i}'

                ingredient_name = request.form.get(ingredient_name_key)
                ingredient_qty = request.form.get(ingredient_qty_key)

                if ingredient_name is None:
                    break

                if ingredient_name.strip() != "":
                    ingredients_list.append({
                        'name': ingredient_name,
                        'quantity_unit': ingredient_qty if ingredient_qty else ''
                    })

                i += 1
            # --- END INGREDIENT LOOP ---
            recipe['ingredients'] = ingredients_list
            conn.close()
            return render_template("add_recipe.html",
                                   recipe=recipe,
                                   categories=all_categories,
                                   selected_category_ids=selected_category_ids_current,
                                   editing=True)

        try:
            # 1. Update recipes table
            cursor.execute(
                """
                UPDATE recipes
                SET title = ?, description = ?, instructions = ?, prep_time = ?, cook_time = ?, image_filename = ?
                WHERE id = ?
                """,
                (title, description, instructions, prep_time,
                 cook_time, image_filename_to_db, recipe_id)
            )

            # 2. Update ingredients: Delete old and insert new
            cursor.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))

            # --- INGREDIENT LOOP HERE ---
            ingredients_list = []
            i = 0
            while True:
                ingredient_name_key = f'ingredient_name_{i}'
                ingredient_qty_key = f'ingredient_qty_{i}'

                ingredient_name = request.form.get(ingredient_name_key)
                ingredient_qty = request.form.get(ingredient_qty_key)

                if ingredient_name is None:
                    break

                if ingredient_name.strip() != "":
                    ingredients_list.append({
                        'name': ingredient_name,
                        'quantity_unit': ingredient_qty if ingredient_qty else ''
                    })

                i += 1
            # --- END INGREDIENT LOOP ---

            for ingredient in ingredients_list:
                if ingredient['name']:
                    cursor.execute(
                        "INSERT INTO ingredients (recipe_id, name, quantity_unit) VALUES (?, ?, ?)",
                        (recipe_id, ingredient['name'], ingredient['quantity_unit'])
                    )

            # 3. Update recipe_categories: Delete old and insert new
            cursor.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", (recipe_id,))
            if selected_category_ids:
                for category_id in selected_category_ids:
                    if cursor.execute("SELECT id FROM categories WHERE id = ?", (category_id,)).fetchone():
                        cursor.execute(
                            "INSERT INTO recipe_categories (recipe_id, category_id) VALUES (?, ?)", (recipe_id, category_id))
                    else:
                        flash(
                            f"Invalid category ID '{category_id}' was selected and ignored.", "warning")

            conn.commit()
            flash("Recipe updated successfully!", "success")
            return redirect(url_for("recipe_detail", recipe_id=recipe_id))

        except sqlite3.Error as e:
            conn.rollback()
            flash(f"An error occurred while updating the recipe: {e}", "danger")
            # --- INGREDIENT LOOP HERE ---
            ingredients_list = []
            i = 0
            while True:
                ingredient_name_key = f'ingredient_name_{i}'
                ingredient_qty_key = f'ingredient_qty_{i}'

                ingredient_name = request.form.get(ingredient_name_key)
                ingredient_qty = request.form.get(ingredient_qty_key)

                if ingredient_name is None:
                    break

                if ingredient_name.strip() != "":
                    ingredients_list.append({
                        'name': ingredient_name,
                        'quantity_unit': ingredient_qty if ingredient_qty else ''
                    })

                i += 1
            # --- END INGREDIENT LOOP ---
            recipe['ingredients'] = ingredients_list
            all_categories = cursor.execute(
                "SELECT id, name FROM categories ORDER BY name").fetchall()
            selected_categories_current = cursor.execute(
                "SELECT category_id FROM recipe_categories WHERE recipe_id = ?", (recipe_id,)).fetchall()
            selected_category_ids_current = [str(cat["category_id"])
                                             for cat in selected_categories_current]
            conn.close()
            return render_template("add_recipe.html",
                                   recipe=recipe,
                                   categories=all_categories,
                                   selected_category_ids=selected_category_ids_current,
                                   editing=True)
        finally:
            if conn:
                conn.close()

    else:  # GET request: Display the form with existing data
        # Fetch existing ingredients and categories for pre-filling
        ingredients = cursor.execute(
            "SELECT name, quantity_unit FROM ingredients WHERE recipe_id = ?",
            (recipe_id,)
        ).fetchall()

        # Fetch all categories to populate the select dropdown
        all_categories = cursor.execute("SELECT id, name FROM categories ORDER BY name").fetchall()

        # Fetch categories currently associated with this recipe to mark them as selected
        selected_categories_current = cursor.execute(
            "SELECT category_id FROM recipe_categories WHERE recipe_id = ?",
            (recipe_id,)
        ).fetchall()
        selected_category_ids = [str(cat["category_id"]) for cat in selected_categories_current]

        # Attach ingredients to the recipe dictionary so the template can access them as recipe.ingredients
        recipe['ingredients'] = ingredients

        conn.close()

        return render_template("add_recipe.html",
                               recipe=recipe,
                               categories=all_categories,
                               selected_category_ids=selected_category_ids,
                               editing=True)


@app.route("/delete_recipe/<int:recipe_id>", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    """Allow user to delete their own recipe."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch the recipe to verify ownership and get the image filename
        recipe = cursor.execute(
            "SELECT user_id, image_filename FROM recipes WHERE id = ?", (recipe_id,)
        ).fetchone()

        if recipe is None or recipe["user_id"] != session["user_id"]:
            flash("Recipe not found or you don't have permission to delete it.", "danger")
            conn.close()
            return redirect(url_for("index"))

        # Get the filename before the database record is deleted
        image_filename = recipe["image_filename"]

        # If an image exists, delete the physical file from the server
        if image_filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError as e:
                    print(f"Error deleting image file {filepath}: {e}")
                    flash(f"Error deleting associated image file: {e}", "warning")

        # Delete all database entries associated with the recipe
        cursor.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
        cursor.execute("DELETE FROM recipe_categories WHERE recipe_id = ?", (recipe_id,))
        cursor.execute("DELETE FROM favorites WHERE recipe_id = ?", (recipe_id,))
        cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))

        conn.commit()
        flash("Recipe deleted successfully!", "success")
        return redirect(url_for("index"))

    except sqlite3.Error as e:
        conn.rollback()
        flash(f"An error occurred while deleting the recipe: {e}", "danger")
        print(f"Database error during delete: {e}")
        return redirect(url_for("recipe_detail", recipe_id=recipe_id))

    finally:
        if conn:
            conn.close()


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow user to change their password."""
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")

        # Input validation
        if not current_password:
            flash("Must provide current password", "danger")
            return render_template("change_password.html")
        if not new_password:
            flash("Must provide new password", "danger")
            return render_template("change_password.html")
        if not confirmation:
            flash("Must confirm new password", "danger")
            return render_template("change_password.html")
        if new_password != confirmation:
            flash("New passwords do not match", "danger")
            return render_template("change_password.html")
        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("change_password.html")
        if new_password == current_password:
            flash("New password cannot be the same as current password", "danger")
            return render_template("change_password.html")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get user's current hash from the database
        cursor.execute("SELECT hash FROM users WHERE id = ?", (session["user_id"],))
        user_data = cursor.fetchone()

        if user_data is None:  # it won't happen
            conn.close()
            flash("User not found.", "danger")
            session.clear()
            return redirect(url_for("login"))

        current_hash = user_data["hash"]

        # Verify current password
        if not check_password_hash(current_hash, current_password):
            conn.close()
            flash("Incorrect current password", "danger")
            print(
                f"DEBUG: Password Change Failed - Incorrect current password for user_id {session['user_id']}")
            return render_template("change_password.html")

        # Hash the new password
        new_hashed_password = generate_password_hash(new_password)
        print(f"DEBUG: Password Change - New hashed password generated.")

        # Update the user's password in the database
        try:
            print(
                f"DEBUG: Password Change - Attempting to UPDATE hash for user_id {session['user_id']}")
            cursor.execute("UPDATE users SET hash = ? WHERE id = ?",
                           (new_hashed_password, session["user_id"]))
            conn.commit()
            print("DEBUG: Password Change - conn.commit() executed successfully.")
            flash("Password changed successfully!", "success")
            return redirect(url_for("index"))
        except sqlite3.Error as e:
            conn.rollback()
            print(f"DEBUG: Password Change - Database error during update: {e}")
            flash(f"An unexpected error occurred: {e}", "danger")
            return render_template("change_password.html")
        finally:
            if conn:
                conn.close()
                print("DEBUG: Password Change - Database connection closed.")

    else:  # GET request
        return render_template("change_password.html")


@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """Allows user to request a password reset token."""
    if request.method == "POST":
        email = request.form.get("email")

        if not email:
            flash("Please provide your email address.", "danger")
            return render_template("forgot_password.html")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if the email exists in the database
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()

        if user:
            user_id = user["id"]
            # Generate a unique token
            token = str(uuid.uuid4())
            # Set token to expire in 5 minutes.
            expires_at = datetime.now() + timedelta(minutes=5)
            expires_at_str = expires_at.isoformat(sep=' ', timespec='seconds')  # Format for SQLite

            try:
                # Store the token in the database
                # Delete any existing tokens for this user to ensure only one active token
                cursor.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
                cursor.execute("INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
                               (user_id, token, expires_at_str))
                conn.commit()

                # --- SIMULATE EMAIL SENDING ---
                print(f"\n--- PASSWORD RESET TOKEN (FOR DEVELOPMENT ONLY) ---")
                print(f"User ID: {user_id}")
                print(f"Token: {token}")
                print(f"Expires at: {expires_at_str}")
                # This is the link user would click
                print(f"Link: {request.url_root}reset_password/{token}")
                print(f"---------------------------------------------------\n")
                # --- END SIMULATION ---

                flash(
                    "If an account with that email exists, a password reset link has been sent to your email.", "info")
                return redirect(url_for("login"))  # Redirect to login or a confirmation page
            except sqlite3.Error as e:
                conn.rollback()
                flash(f"An unexpected error occurred: {e}", "danger")
                return render_template("forgot_password.html")
            finally:
                conn.close()
        else:
            # IMPORTANT!!! give a generic message to prevent user enumeration
            flash("If an account with that email exists, a password reset link has been sent to your email.", "info")
            return redirect(url_for("login"))  # Redirect to login even if email not found

    else:  # GET request
        # --- Create a response object to add headers ---
        response = make_response(render_template("forgot_password.html"))
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    print(f"--- DEBUG: Entered reset_password route for token: {token} ---")
    print(f"--- DEBUG: Request method: {request.method} ---")
    print(f"--- DEBUG: Current user_id in session: {session.get('user_id')} ---")

    if request.method == "GET":
        print("--- DEBUG: Processing GET request for reset_password ---")

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT user_id, expires_at FROM password_reset_tokens WHERE token = ?", (token,))
        token_data = cursor.fetchone()
        conn.close()

        print(f"--- DEBUG: Token data from DB: {token_data} ---")
        if not token_data:
            print("--- DEBUG: Token NOT found in DB. ---")
            flash("Invalid or expired password reset link. Please request a new one.", "danger")
            return redirect(url_for("forgot_password"))

        expires_at_dt = datetime.fromisoformat(token_data["expires_at"])
        current_time = datetime.now()
        print(f"--- DEBUG: Token expires at: {expires_at_dt} ---")
        print(f"--- DEBUG: Current time: {current_time} ---")

        if expires_at_dt < current_time:
            print("--- DEBUG: Token HAS expired. ---")
            flash("Invalid or expired password reset link. Please request a new one.", "danger")
            return redirect(url_for("forgot_password"))

        print("--- DEBUG: Token is VALID and NOT expired. Rendering reset_password.html ---")
        return render_template("reset_password.html", token=token)

    else:  # request.method == "POST"
        print("--- DEBUG: Processing POST request for reset_password ---")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")

        if not new_password or not confirmation:
            flash("Please provide and confirm your new password.", "danger")
            return render_template("reset_password.html", token=token)

        if new_password != confirmation:
            flash("New password and confirmation do not match.", "danger")
            return render_template("reset_password.html", token=token)

        if len(new_password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("reset_password.html", token=token)

        # Re-validate the token for the POST request
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT user_id, expires_at FROM password_reset_tokens WHERE token = ?", (token,))
            token_data = cursor.fetchone()

            if not token_data or datetime.fromisoformat(token_data["expires_at"]) < datetime.now():
                flash("Invalid or expired password reset link. Please request a new one.", "danger")
                if token_data:
                    cursor.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
                conn.commit()
                return redirect(url_for("forgot_password"))  # Redirect to request a new link

            user_id = token_data["user_id"]

            hashed_password = generate_password_hash(new_password)
            cursor.execute("UPDATE users SET hash = ? WHERE id = ?", (hashed_password, user_id))

            # Delete the used password reset token from the database
            cursor.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
            conn.commit()

            flash("Your password has been successfully reset. Please log in with your new password.", "success")
            return redirect(url_for("login"))

        except sqlite3.Error as e:
            conn.rollback()
            flash(f"An unexpected error occurred during password reset: {e}", "danger")
            return render_template("reset_password.html", token=token)
        finally:
            conn.close()


@app.route("/toggle_favorite", methods=["POST"])
@login_required
def toggle_favorite():
    recipe_id = request.form.get("recipe_id")
    user_id = session["user_id"]

    if not recipe_id:
        flash("Invalid recipe.", "error")
        return redirect(request.referrer or "/")  # Go back to the page user came from

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the recipe is already favorited by the user
    cursor.execute("SELECT * FROM favorites WHERE user_id = ? AND recipe_id = ?",
                   (user_id, recipe_id))
    favorite = cursor.fetchone()

    if favorite:
        # If already favorited, unfavorite it (delete from table)
        cursor.execute("DELETE FROM favorites WHERE user_id = ? AND recipe_id = ?",
                       (user_id, recipe_id))
        conn.commit()
        flash("Recipe removed from favorites!", "success")
        redirect_to_favorites = True
    else:
        # If not favorited, favorite it (insert into table)
        cursor.execute("INSERT INTO favorites (user_id, recipe_id) VALUES (?, ?)",
                       (user_id, recipe_id))
        conn.commit()
        flash("Recipe added to favorites!", "success")
        redirect_to_favorites = False

    conn.close()

    if redirect_to_favorites:
        return redirect(url_for('favorites'))
    else:
        return redirect(request.referrer or "/")


@app.route("/favorites")
@login_required
def favorites():
    """Display a list of recipes favorited by the current user."""
    user_id = session["user_id"]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch recipes that the current user has favorited
    # I need to join them with 'recipes' table to get all recipe details
    # and join with the 'users' table to get the owner's username
    cursor.execute("""
        SELECT
            r.id, r.title, r.description, r.prep_time, r.cook_time, r.image_filename,
            r.user_id, u.username AS owner_username,
            CASE WHEN r.user_id = ? THEN 1 ELSE 0 END AS is_current_user_owner
        FROM favorites f
        JOIN recipes r ON f.recipe_id = r.id
        JOIN users u ON r.user_id = u.id
        WHERE f.user_id = ?
        ORDER BY r.title
    """, (user_id, user_id))  # Pass user_id twice for the CASE WHEN and WHERE clauses

    favorite_recipes = cursor.fetchall()
    conn.close()

    # Pass system_user_id if needed for "By: (Default)"
    return render_template("favorites.html", recipes=favorite_recipes, system_user_id=1)


if __name__ == "__main__":
    app.run(debug=True)
