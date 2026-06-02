from flask import Flask
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, UserMixin, LoginManager, login_required, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import sqlalchemy as sa 
#.venv\Scripts\activate.bat

class Base(DeclarativeBase):
    pass

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.sqlite3'
app.config['SECRET_KEY'] = 'key'

db = SQLAlchemy(app, model_class=Base)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class User(db.Model, UserMixin):
    _id: Mapped[int] = mapped_column("id", sa.Integer, primary_key=True)
    username: Mapped[str] = mapped_column(sa.String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    def get_id(self):
        return str(self._id)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
    

@app.route("/")
def home_page():
    return render_template("home.html")


@app.route("/signup", methods=["POST", "GET"])
def signup():
    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        
        user_exists = db.session.execute(db.select(User).filter_by(username=username)).scalar()
        if user_exists:
            flash('Username is taken', category='error')
            return redirect(url_for('signup'))
        
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created!', category='success')
        print('accnt created')
        return redirect(url_for('login'))


    return render_template("signup.html")

@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":

        username = request.form.get('username')
        password = request.form.get('password')

        user = db.session.execute(db.select(User).filter_by(username=username)).scalar()

        if user and user.password == password:
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash("invalid username or password", category='error')


    return render_template("login.html")

@app.route("/dashboard", methods=["POST", "GET"])
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/logout")
@login_required

def logout():
    logout_user()
    print("logged out")
    return redirect(url_for(home_page))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)