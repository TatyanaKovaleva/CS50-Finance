from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    stocks=[]
    rows = db.execute("SELECT Symbol,Name,SUM(Shares) FROM Stock GROUP BY Symbol HAVING id = :id",id = session["user_id"])
    info = db.execute("SELECT cash FROM users WHERE id = :id",id = session["user_id"])
    cash = info[0]["cash"]
    total =0
    for row in rows:
        quote = lookup(row["Symbol"])
        stock={
            "symbol": row["Symbol"],
            "name": row["Name"],
            "shares":row["SUM(Shares)"],
            "price": quote['price'],
        }
        total = total+(quote['price']*row["SUM(Shares)"])
        stocks.append(stock)
    total = total+cash
    return render_template("index.html",stocks= stocks,cash = usd(cash),total = usd(total)) 

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("must provide symbol/shares")
        quote  = lookup(request.form.get("symbol"))
        if not quote:
            return apology("invalid symbol")
        if float(request.form.get("shares"))<0 or not float(request.form.get("shares")).is_integer():
            return apology("invalid shares")
        row = db.execute("SELECT cash FROM users WHERE id = :id",id = session["user_id"])
        if row[0]["cash"]<(quote['price'])*(float(request.form.get("shares"))):
            return apology("Not enough money")
        else:
            db.execute("INSERT INTO Stock (id,Symbol,Name,Price,Shares) VALUES (:id,:symbol,:name,:price,:share)",id = session["user_id"],symbol =quote['symbol'],name = quote['name'],price = quote['price'],share =request.form.get("shares") );
            db.execute("UPDATE users set cash = :cash-:total WHERE id = :id",cash = row[0]["cash"],total =(quote['price']*float(request.form.get("shares"))),id = session["user_id"]);
            return redirect(url_for("index"))
    else:
        return render_template("buy.html")
        
        
@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    history = []
    rows= db.execute("SELECT * FROM Stock where id = :id",id = session["user_id"])
    for row in rows:
        his={
            "symbol": row["Symbol"],
            "shares": row["Shares"],
            "price": row["Price"],
            "date": row["date"]
        }
        history.append(his)
    return render_template("history.html",history=history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not  request.form.get("symbol"):
            return apology("must provide symbol")
        quote  = lookup(request.form.get("symbol"))
        if not quote :
            return apology("Invalid Symbol")
            
        return render_template("quoted.html",name=quote['name'],price=usd(quote['price']),symbol = quote['symbol'])
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password")==request.form.get("repassword"):
            return apology("Password entered doesn't match!!")
        hash = pwd_context.encrypt(request.form.get("password"))
        result = db.execute("INSERT INTO users (username,hash) VALUES (:username,:hash)",username=request.form.get("username"),hash=hash)
        if not result:
            return apology("Username already exist")
            
        # remember which user has logged in
        session["user_id"] = db.execute("SELECT id FROM users WHERE username = :username", username=request.form.get("username"))

        # redirect user to home page
        return redirect(url_for("index"))
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("must provide symbol/shares")
        quote  = lookup(request.form.get("symbol"))
        if not quote:
            return apology("invalid symbol")
        if float(request.form.get("shares"))<0 or not float(request.form.get("shares")).is_integer():
            return apology("invalid shares")
        row = db.execute("SELECT cash FROM users where id = :id",id = session["user_id"]);
        sym = db.execute("SELECT Symbol FROM Stock where id = :id",id = session["user_id"]);
        if quote['symbol'] not in sym[0]["Symbol"]:
            return apology("Share not owned")
        shares = db.execute("SELECT SUM(Shares) FROM Stock GROUP BY Symbol HAVING Symbol = :Symbol ",Symbol =quote['symbol'] )

        if shares[0]["SUM(Shares)"] < float(request.form.get("shares")):
            return apology("Too many shares")
        db.execute("UPDATE users SET cash = :cash+:total WHERE id = :id",cash = row[0]["cash"],total =(quote['price']*float(request.form.get("shares"))),id = session["user_id"]);
        db.execute("INSERT INTO Stock (id,Symbol,Name,Price,Shares) VALUES (:id,:symbol,:name,:price,:share)",id = session["user_id"],symbol =quote['symbol'],name = quote['name'],price =quote['price'],share =(-1)*float(request.form.get("shares")) );
        return redirect(url_for("index"))
    else:
        return render_template("sell.html")
        
        
@app.route("/passchange", methods=["GET", "POST"])
@login_required
def passchange():
    if request.method=="POST":
        if not (request.form.get("old") or request.form.get("new") or request.form.get("renew")):
            return apology("Enter all fields")
        rows = db.execute("SELECT hash FROM users WHERE id = :id", id = session['user_id'])
        if not pwd_context.verify(request.form.get("old"), rows[0]["hash"]):
            return apology("Incorrect old password")
        if not request.form.get("new")==request.form.get("renew"):
            return apology("Passwords entered doesn't match")
        hash = pwd_context.encrypt(request.form.get("new"))
        db.execute("UPDATE users set hash=:hash WHERE id = :id",hash=hash,id = session["user_id"])
        return render_template("psuccess.html")
    else:
        return render_template("passchange.html")
            
        
        

        
            
            
            
            
            
            
            
