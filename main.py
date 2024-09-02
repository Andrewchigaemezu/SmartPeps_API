from flask import Flask, request, send_from_directory, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from flask import jsonify
from flask_cors import CORS
import random
from datetime import timedelta, datetime
import time
import os
import base64
from flask_login import LoginManager, UserMixin, login_required, login_user

from flask_jwt_extended import create_access_token, jwt_required, JWTManager, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('API_KEY')
jwt = JWTManager(app)
CORS(app)


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URI", "sqlite:///smartpeps_store.db")
db.init_app(app)




UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



class Seller(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    products = db.relationship('Product', backref='seller', lazy=True)


class Product(db.Model):
    product_id: Mapped[int] = mapped_column(primary_key=True)
    product_title: Mapped[str] = mapped_column(nullable=False)
    product_price: Mapped[float] = mapped_column(nullable=False)
    product_image: Mapped[str] = mapped_column(nullable=False)
    product_description: Mapped[str] = mapped_column(nullable=False)
    product_category: Mapped[str] = mapped_column(nullable=False)
    product_type: Mapped[str] = mapped_column(nullable=False)
    product_size: Mapped[str] = mapped_column(nullable=False)
    product_color: Mapped[str] = mapped_column(nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('seller.id'), nullable=False)


with app.app_context():
    db.create_all()


@app.route("/")
def home():
    return "<p>Hello World</p>"



# GET SELLER
@app.route('/fetch_affiliate/<int:seller_id>', methods=["POST", "GET"])
@jwt_required()
def load_seller(seller_id):
    find_seller_detail = db.session.execute(db.select(Seller).where(Seller.id == seller_id))
    seller_detail = find_seller_detail.scalar()
    if seller_detail:
        response = jsonify(
            username=seller_detail.username,
            email=seller_detail.email,
            id=seller_detail.id,
        )
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    else:
        return jsonify(error={"Invalid User": "This user does not exist."}), 404


# SIGNING AFFILIATE UP
@app.route('/create_account', methods=["POST", "GET"])
def add_seller():
    data = request.get_json()
    if "username" in data and "email" in data and "password" in data:
        new_seller = Seller(
            username=data["username"],
            email=data["email"],
            password=generate_password_hash(data["password"], "pbkdf2:sha256", 8)
        )
        user_exists = db.session.query(db.exists().where(Seller.email == data['email'])).scalar()
        if user_exists:
            return jsonify(
                error={"Invalid Request": "Affiliate email already exists."}), 404
        else:
            expires = timedelta(days=1)

            access_token = create_access_token(identity=new_seller.email, expires_delta=expires)
            if access_token:

                db.session.add(new_seller)
                db.session.commit()
                find_seller_detail = db.session.execute(db.select(Seller).where(Seller.email == data["email"]))
                seller_detail = find_seller_detail.scalar()
                response = jsonify(
                    username=seller_detail.username,
                    email=seller_detail.email,
                    id=seller_detail.id,
                    token={"access_token": access_token},
                    message={"Seller account created": "You have successfully created an affiliate account"}
                )
                response.headers.add("Access-Control-Allow-Origin", "*")
                return response
            else:
                return jsonify(
                    error={"Unauthorized": "Access token failed"}), 401

    else:
        return jsonify(error={"Invalid Request": "Please provide valid credentials to sign up as an affiliate."}), 404


# LOG AFFILIATE IN
@app.route("/login", methods=["POST", "GET"])
def login_seller():
    data = request.get_json()
    if "password" in data and "email" in data:
        result = db.session.execute(db.select(Seller).where(Seller.email == data["email"]))
        seller = result.scalar()
        if check_password_hash(seller.password, data["password"]):
            expires = timedelta(days=1)
            access_token = create_access_token(identity=seller.email, expires_delta=expires)
            if access_token:
                return jsonify(
                    username=seller.username,
                    email=seller.email,
                    id=seller.id,
                    token={"access_token": access_token},
                    message={"success": "Logged in successfully"}
                )
            else:
                return jsonify(
                    error={"Unauthorized": "Access token failed"}), 401
        else:
            return jsonify(message={"Incorrect email or Password"})
    else:
        return jsonify(error={"Invalid User": "Please provide user details."}), 404


# FETCH AFFILIATE PRODUCTS
@app.route("/seller_products")
@jwt_required()
def get_seller_products():
    query_parameter = request.args.get("email")
    find_seller = db.session.execute(db.select(Seller).where(Seller.email == query_parameter))
    seller = find_seller.scalar()
    if seller:
        result = db.session.execute(db.select(Product).where(Product.seller_id == seller.id))
        all_products = result.scalars().all()
        product_list = [
            {
            "id": product.product_id,
            "product_title": product.product_title,
            "product_price": product.product_price,
            "product_image": f"http://127.0.0.1:5000{url_for('static', filename=f'images/{product.product_image}')}",
            "product_description": product.product_description,
            "product_category": product.product_category,
            "product_type": product.product_type,
            "product_size": product.product_size,
            "product_color": product.product_color
        }
            for product in all_products]
        response = jsonify(product_list)
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    else:
        return jsonify(error={"Invalid Request": "Please specify which seller id to fetch seller products"}), 404





def generate_unique_filename():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"smartpeps_image_{timestamp}."





# ADD PRODUCTS FOR SALE
@app.route('/add_product', methods=["POST", "GET"])
@jwt_required()
def add_product():
    data = request.get_json()
    if "seller_email" in data:
        seller = Seller.query.filter_by(email=data["seller_email"]).first()
        print(seller)
        if "category" in data and "title" in data and "price" in data and "image" in data and "description" in data\
                and "type" in data and "size" in data and "color" in data:
            file_extension = data["extension"]
            image_data = data["image"]
            image_bytes = base64.b64decode(image_data)
            file_name = f"{generate_unique_filename()}{file_extension}"
            with open(os.path.join(app.config['UPLOAD_FOLDER'], file_name), 'wb') as f:
                f.write(image_bytes)

            new_product = Product(
                product_category=data["category"].title(),
                product_title=data["title"].title(),
                product_price=data["price"],
                seller_id=seller.id,
                product_image=file_name,
                product_description=data["description"].capitalize(),
                product_type=data["type"].title(),
                product_size=data["size"],
                product_color=data["color"].title()
            )
            db.session.add(new_product)
            db.session.commit()
            return jsonify(response={"Success": "Successfully added the new product."}), 200
        else:
            return jsonify(error={"Invalid Data": "Please provide valid product data to be uploaded."}), 404
    else:
        return jsonify(error={"Invalid User": "Couldn't find seller associated with the provided email."}), 404


# UPDATE A PRODUCT BY AN AFFILIATE
@app.route("/update_product/<int:product_id>", methods=["PUT", "POST", "GET"])
@jwt_required()
def patch_product(product_id):
    product = Product.query.get_or_404(product_id)
    data = request.get_json()
    if product:
        if 'title' in data:
            product.product_title = data['title'].title()
        if 'price' in data:
            product.product_price = data['price']
        if 'description' in data:
            product.product_description = data['description'].capitalize()
        if "category" in data:
            product.product_category = data["category"].title()
        if "type" in data:
            product.product_type = data["type"]
        if "size" in data:
            product.product_size = data["size"]
        if "color" in data:
            product.product_color = data["color"]
        if data["image"] == "":
            product.product_image = product.product_image
        else:
            image_path = f"static/images/{product.product_image}"
            os.remove(image_path)
            file_extension = data["extension"]
            image_data = data["image"]
            image_bytes = base64.b64decode(image_data)
            file_name = f"{generate_unique_filename()}{file_extension}"
            with open(os.path.join(app.config['UPLOAD_FOLDER'], file_name), 'wb') as f:
                f.write(image_bytes)
            product.product_image = file_name
        db.session.commit()

        return jsonify(response={"success": "Successfully updated product."}), 200
    else:
        return jsonify(error={"Not Found": "Sorry we couldn't find a product with that id."}), 404


# DELETE A PRODUCT BY AN AFFILIATE
@app.route("/delete_product/<int:product_id>", methods=["DELETE","GET", "POST"])
@jwt_required()
def delete_product(product_id):
    api_key = request.args.get("api_key")
    if api_key == "TopSecretAPIKey":
        product = db.get_or_404(Product, product_id)
        if product:
            image_path = f"static/images/{product.product_image}"
            os.remove(image_path)
            db.session.delete(product)
            db.session.commit()
            return jsonify(response={"success": "Successfully deleted the product from the database."}), 200
        else:
            return jsonify(error={"Not Found": "Sorry a product with that id was not found in the database."}), 404
    else:
        return jsonify(error={"Forbidden": "Sorry, that's not allowed. Make sure you have the correct api_key."}), 403


# FETCH ALL PRODUCTS
@app.route("/all_products")
def get_all_products():
    result = db.session.execute(db.select(Product))
    all_products = result.scalars().all()
    product_list = [{
            "id": product.product_id,
            "product_title": product.product_title,
            "product_price": product.product_price,
            "product_image": f"http://127.0.0.1:5000{url_for('static', filename=f'images/{product.product_image}')}",
            "product_description": product.product_description,
            "product_category": product.product_category,
            "product_type": product.product_type,
            "product_size": product.product_size,
            "product_color": product.product_color
        } for product in all_products]
    # print(product_list)
    response = jsonify(product_list)
    response.headers.add("Access-Control-Allow-Origin", "*")
    # time.sleep(5)
    return response


# GET PRODUCTS DETAILS  BY ID
@app.route("/product_detail/<int:product_id>")
def product_detail(product_id):
    result = db.session.execute(db.select(Product).where(Product.product_id == product_id))
    product = result.scalar()
    # print(product)
    if product:
        response =  [{
            "id": product.product_id,
            "product_title": product.product_title,
            "product_price": product.product_price,
            "product_image": f"http://127.0.0.1:5000{url_for('static', filename=f'images/{product.product_image}')}",
            "product_description": product.product_description,
            "product_category": product.product_category,
            "product_type": product.product_type,
            "product_size": product.product_size,
            "product_color": product.product_color
        }]
        return response
    else:
        return jsonify(error={"Not Found": "Sorry a product with that id was not found in the database."}), 404


# SEARCH PRODUCTS BY CATEGORY
@app.route("/search")
def search_product():
    query_category = request.args.get("category").title()
    result = db.session.execute(db.select(Product).where(Product.product_category == query_category))
    search_result = result.scalars().all()
    if search_result:
        search_list = [{
            "id": result.product_id,
            "product_title": result.product_title,
            "product_price": result.product_price,
            "product_image": f"http://127.0.0.1:5000{url_for('static', filename=f'images/{result.product_image}')}",
            "product_description": result.product_description,
            "product_category": result.product_category,
            "product_type": result.product_type,
            "product_size": result.product_size,
            "product_color": result.product_color
        } for result in search_result]
        response = jsonify(search_list)
        response.headers.add("Access-Control-Allow-Origin", "*")
        return response
    else:
        empty_list = []
        response = jsonify(empty_list)
        return empty_list
        # return jsonify(error={"Not Found": "Sorry, we don't have products in that category."}), 404





if "__main__" == __name__:
    app.run(debug=False)
