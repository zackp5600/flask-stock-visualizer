from flask import Flask
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, UserMixin, LoginManager, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import sqlalchemy as sa 
import yfinance as yf
import pandas as pd
import time
from datetime import datetime
import os
import json
import math
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
    
    stocks: Mapped[list["Portfolio"]] = db.relationship("Portfolio", backref="owner", lazy=True)


    def get_id(self):
        return str(self._id)

class Portfolio(db.Model):
    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    shares: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    avg_price: Mapped[float] = mapped_column(sa.Numeric(10,2), nullable=False)

    #connects stocks to specfic user id
    user_id: Mapped[int] = mapped_column(sa.ForeignKey('user.id'),nullable=False)




#yfinance funcs

def download_symbol(symbol, user_id):
    today = datetime.now()
    start_date = today.replace(year=today.year-1).strftime("%Y-%m-%d")
    current_date = today.strftime("%Y-%m-%d")
    
    # Create a unique folder for this specific user's stock CSVs
    user_folder = f"./symbols/user_{user_id}"
    os.makedirs(user_folder, exist_ok=True)
    
    # Download data from Yahoo Finance
    data = yf.download(symbol, period="1y", multi_level_index=False)
    
    if data.empty:
        return False
        
    # Save CSV into the user's isolated folder
    csv_path = f"{user_folder}/{symbol}.csv"
    data.to_csv(csv_path, float_format="%.2f")
    return True


#website pages/links

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



#place that shows ur portfolio and stuff about it

@app.route("/dashboard", methods=["POST", "GET"])
@login_required
def dashboard():
    if request.method == "POST":
        ticker_symbol = request.form.get("ticker").strip().upper()
        shares = int(request.form.get("shares"))
        avg_price = float(request.form.get("avg_price"))
        print(shares, avg_price)

        already_tracked = db.session.execute(
            db.select(Portfolio).filter_by(symbol=ticker_symbol, user_id=current_user._id)
        ).scalar()



        if already_tracked:
            flash(f"{ticker_symbol} is already in your portfolio!", category='error')
            print("already in portfolio!")
            return redirect(url_for('dashboard'))
        

        try:
            download_symbol(ticker_symbol, current_user._id)

            print("jlkafjdfklajd")
            if download_symbol:
                new_stock = Portfolio(symbol=ticker_symbol,shares=shares, avg_price=avg_price ,user_id=current_user._id)
                print("done")
                db.session.add(new_stock)
                db.session.commit()
            else:
                print("error!!!")

        except:
            print('error with tickery sysmbol')

        return redirect(url_for("dashboard"))

    user_portfolio = current_user.stocks

    if user_portfolio: #stocks saved to user
        market_value = 0
        for z in range(len(current_user.stocks)):
            df = pd.read_csv(f"./symbols/user_{current_user._id}/{current_user.stocks[z].symbol}.csv")
            labels=df['Date'].tolist()
            values=df['Close'].tolist()
            values = [0] * len(values) #make values list all zero works
            #this lowk might be why its not working prop

            total_alloc = 0
            # for stock in current_user.stocks:

            total_alloc+= current_user.stocks[z].shares * current_user.stocks[z].avg_price


            #get market value for stocks
            # for stock in current_user.stocks:

            Ticker = yf.Ticker(current_user.stocks[z].symbol)
            current_price = Ticker.info.get("currentPrice")
            market_value += current_user.stocks[z].shares * current_price
            
            #get portfolio values
            # for i in range(len(current_user.stocks)):
                #get specific stock
            df = pd.read_csv(f"./symbols/user_{current_user._id}/{current_user.stocks[z].symbol}.csv", index_col='Date', parse_dates=True)
            
            #get price of stock at certain date and add it to the values
            for j in range(len(labels)):
                # print(df.loc[labels[j], 'Close'])
                spec_price = df.loc[labels[j], 'Close']
                values[j] += spec_price * current_user.stocks[z].shares

        total_alloc = round(total_alloc, 2)

    else: #stocks not saved to user yet
        labels=0
        values=0
        return render_template("dashboard.html", portfolio=user_portfolio, user=current_user, labels=labels, values=values)

        
    return render_template("dashboard.html", portfolio=user_portfolio, user=current_user, csv=df, labels=labels, values=values,total_alloc=total_alloc, market_value=market_value)





@app.route("/logout")
@login_required
def logout():
    logout_user()
    print("logged out")
    return redirect(url_for('home_page'))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)