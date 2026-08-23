import json
import math
import os
import time
from datetime import datetime

import pandas as pd
import sqlalchemy as sa
import yfinance as yf
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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
    failed = False

    if request.method == "POST":
        ticker_symbol = request.form.get("ticker").strip().upper()
        shares = int(request.form.get("shares"))
        avg_price = float(request.form.get("avg_price"))

        #checks if stock ticker is in db for the user
        already_tracked = db.session.execute(
            db.select(Portfolio).filter_by(symbol=ticker_symbol, user_id=current_user._id)
        ).scalar()

        if already_tracked: # if the stock is already saved in the users portfolio tell the user
            flash(f"{ticker_symbol} is already in your portfolio!", category='error')
            print("already in portfolio!")
            return redirect(url_for('dashboard'))   

        try: # if the stock is not already saved in the users portfolio then download it

            x = download_symbol(ticker_symbol, current_user._id) # x downloads the ticker while also returning if there was any errors with the ticker symbol

            if x:  
                new_stock = Portfolio(symbol=ticker_symbol,shares=shares, avg_price=avg_price ,user_id=current_user._id)
                print("done")
                db.session.add(new_stock) # add the stock to the db
                db.session.commit()
                
            else: # failed to download the stock, probably becuase it was invalid ticker
                failed = True
                flash(f"Ticker symbol {ticker_symbol} is invalid!", category='ticker_error')

        except:
            print('error with tickery sysmbol')#idk why i put this here, this only happens if there is an error with the code

        return redirect(url_for("dashboard"))

    user_portfolio = current_user.stocks #stocks saved to user

    if user_portfolio: 
        market_value = 0
        df = pd.read_csv(f"./symbols/user_{current_user._id}/{current_user.stocks[0].symbol}.csv")
        values=df['Close'].tolist()
        values = [0.0] * len(values) #make values list all zero works

        total_alloc = 0
        for z in range(len(current_user.stocks)): #iterate through all stocks in users portfolio from the database
            df = pd.read_csv(f"./symbols/user_{current_user._id}/{current_user.stocks[z].symbol}.csv")
            labels=df['Date'].tolist()
            
            #get market value for stocks
            #make ts into a functions sooon 
            Ticker = yf.Ticker(current_user.stocks[z].symbol)
            total_alloc+= current_user.stocks[z].shares * current_user.stocks[z].avg_price

            todays_prices = Ticker.history(period="1d", interval="1m")
            current_price = todays_prices['Close'].iloc[-1]
            
            market_value += current_user.stocks[z].shares * current_price
            market_value = round(market_value, 2)
            
            #get portfolio values
            #get specific stock
            df = pd.read_csv(f"./symbols/user_{current_user._id}/{current_user.stocks[z].symbol}.csv", index_col='Date', parse_dates=True)
            #get price of stock at certain date and add it to the values
            for j in range(len(labels)): #adding values for the graph to show portfolio performance
                current_date = labels[j] 
                # 2. Check if the date exists in this specific stock's file to prevent KeyError
                if current_date in df.index:
                    spec_price = df.loc[current_date, 'Close']
                    add = spec_price * current_user.stocks[z].shares
                    values[j] += add

        # for i in range(len(values)):
            
        #     low = values[i] #finds the 52 week low for the portfolio 
            
        
        total_alloc = round(total_alloc, 2)
        percent_gain = round( (market_value / float(total_alloc)  - 1) * 100, 2)
        dollar_gain = round(market_value - float(total_alloc), 2)


    else: #stocks not saved to user yet
        labels=0
        values=0
        return render_template("dashboard.html", portfolio=user_portfolio, user=current_user, labels=labels, values=values)
    
    return render_template("dashboard.html", portfolio=user_portfolio, user=current_user, csv=df, labels=labels, values=values,total_alloc=total_alloc, market_value=market_value, failed=failed, percent_gain=percent_gain, dollar_gain=dollar_gain)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    print("logged out")
    return redirect(url_for('home_page'))

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=False)