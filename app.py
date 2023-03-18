from flask import *
from mysql.connector import pooling
import jwt
import requests
import os
from datetime import datetime, date
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True

connection_pool = pooling.MySQLConnectionPool(pool_name="pynative_pool",
                                              pool_size=5,
                                              pool_reset_session=True,
                                              host="localhost",
                                              user="",
                                              password="",
                                              database="travel")

# Pages


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/attraction/<id>")
def attraction(id):
    return render_template("attraction.html")


@app.route("/booking")
def booking():
    return render_template("booking.html")


@app.route("/thankyou")
def thankyou():
    return render_template("thankyou.html")


@app.route("/member")
def member():
    return render_template("member.html")

# Order


@app.route("/api/orders", methods=["POST"])
def orders():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor()
        try:
            auth = jwt.decode(request.cookies.get('Set-Cookie'),
                              'secret', algorithms=['HS256'])
        except:
            response = jsonify(error=True, message="請先登入後再操作"), 403
            response.delete_cookie("Set-Cookie")
            return response

        formatted_phone_number = "+886" + \
            request.json.get("contact")["phone"][1:]

        sql = "INSERT INTO bills (person,contactemail,phone) VALUES (%s, %s, %s)"
        val = (request.json.get("contact")["name"], request.json.get(
            "contact")["email"], request.json.get("contact")["phone"])
        mycursor.execute(sql, val)
        mydb.commit()

        sql = "SELECT SUM(price) FROM trip_order WHERE member_id = %s AND bill_id IS NULL"
        val = ([auth['id']])
        mycursor.execute(sql, val)
        price = mycursor.fetchall()
        data = {
            "prime": request.json.get("prime"),
            "partner_key": "",
            "merchant_id": "shalala_CTBC",
            "details": "TapPay Test",
            "amount": int(price[0][0]),
            "cardholder": {
                "phone_number": formatted_phone_number,
                "name": request.json.get("contact")["name"],
                "email": request.json.get("contact")["email"]
            },
            "remember": True
        }

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': os.getenv("APIKEY")
        }
        response = requests.post(
            "https://sandbox.tappaysdk.com/tpc/payment/pay-by-prime",
            json=data, headers=headers)

        mycursor.execute("SELECT LAST_INSERT_ID() FROM bills")
        id = mycursor.fetchall()
        now = datetime.now()
        time_str = now.strftime('%H%M%S')
        today = date.today()
        date_str = today.strftime('%Y%m%d')
        datetime_str = date_str + time_str + str(id[0][0])
        if response.status_code == 200:
            sql = "UPDATE trip_order SET bill_id = %s WHERE member_id = %s AND bill_id IS NULL "
            val = id[0][0], auth['id']

            mycursor.execute(sql, val)
            mydb.commit()
            sql = "UPDATE bills SET payment=1 , number = %s ,price =%s,member_id=%s WHERE id = %s"
            val = datetime_str, int(price[0][0]), auth['id'], id[0][0]
            mycursor.execute(sql, val)
            mydb.commit()
            data = {
                "number": datetime_str,
                "payment": 1,
                "message": "付款成功"
            }
            return jsonify(data=data)
        else:
            data = {
                "number": datetime_str,
                "payment": 0,
                "message": "付款失敗"
            }
            return jsonify(data=data)
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


@app.route("/api/order/<number>")
def order(number):
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor(buffered=True)
        try:
            auth = jwt.decode(request.cookies.get('Set-Cookie'),
                              'secret', algorithms=['HS256'])
        except:
            response = jsonify(error=True, message="請先登入後再操作"), 403
            response.delete_cookie("Set-Cookie")
            return response
        sql = "SELECT trip_order.sight_id,trip_order.date,trip_order.time,bills.person,bills.contactemail,bills.phone,bills.payment,bills.number,bills.price,trip_order.member_id FROM trip_order JOIN bills ON bill_id = bills.id WHERE number = %s"
        val = [number]
        mycursor.execute(sql, val)
        orders = mycursor.fetchall()
        if auth["id"] == orders[0][9]:
            trip = []
            for item in range(0, len(orders)):
                sql = "SELECT id,name,address,image FROM sight JOIN images ON sight_id=sight.id WHERE id= %s"
                val = [orders[item][0]]
                mycursor.execute(sql, val)
                sightmeg = mycursor.fetchone()
                trip += {
                    "attraction":
                    {"id": sightmeg[0],
                     "name": sightmeg[1],
                     "address": sightmeg[2],
                     "image": sightmeg[3]},
                    "date": orders[item][1],
                    "time": orders[item][2]
                },
            data = {
                "number": orders[0][7],
                "price": orders[0][8],
                "trip": trip,
                "contact": {
                    "name": orders[0][3],
                    "email": orders[0][4],
                    "phone": orders[0][5],
                },
                "status": orders[0][6]
            }
            return jsonify(data=data)
        else:
            return jsonify(error=True, message="查無此訂單")
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


# Auth APIs
@app.route("/api/user", methods=["POST"])
def user():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor()
        sql = "SELECT email FROM member WHERE email=(%s)"
        val = ([request.json.get("email")])
        mycursor.execute(sql, val)
        authemail = mycursor.fetchone()
        if authemail != None:
            return jsonify(error=True, message="電子信箱已被註冊"), 400
        else:
            sql = "INSERT INTO member (name,email,password) VALUES (%s, %s, %s)"
            val = (request.json.get("name"), request.json.get(
                "email"), request.json.get("password"))
            mycursor.execute(sql, val)
            mydb.commit()
            return jsonify(ok=True)
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


@app.route("/api/user/auth", methods=["GET", "PUT", "DELETE"])
def auths():
    if request.method == "GET":
        try:
            auth = jwt.decode(request.cookies.get(
                'Set-Cookie'), 'secret', algorithms=['HS256'])
            return jsonify(data=auth)
        except:
            response = jsonify(error=True)
            response.delete_cookie("Set-Cookie")
            return response
    elif request.method == "PUT":
        try:
            mydb = connection_pool.get_connection()
            mycursor = mydb.cursor()
            sql = "SELECT * FROM member WHERE email=(%s)"
            val = ([request.json.get("email")])
            mycursor.execute(sql, val)
            authdata = mycursor.fetchone()
            if authdata == None:
                return jsonify(error=True, message="電子信箱未註冊或輸入錯誤"), 400
            elif authdata[3] == request.json.get("password"):
                auth = jwt.encode({
                    "id": authdata[0],
                    "name": authdata[1],
                    "email": authdata[2],
                    "phone": authdata[5],
                    "pic": authdata[4]
                }, 'secret', algorithm='HS256')
                response = jsonify(ok=True)
                response.set_cookie("Set-Cookie", value=auth, max_age=604800)
                return response
            else:
                return jsonify(error=True, message="密碼輸入錯誤"), 400
        except:
            return jsonify(error=True, message="connection fail"), 500

        finally:
            mycursor.close()
            mydb.close()
    elif request.method == "DELETE":
        response = jsonify(ok=True)
        response.delete_cookie("Set-Cookie")
        return response


# Attraction APIs
@app.route("/api/attractions")
def attractions():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor()
        meg = []

        page = request.args.get("page")
        if page == None:
            page = 0
        try:
            page = int(page)
        except:
            return jsonify(error=True, message="page must be int"), 500
        keyword = request.args.get("keyword")
        if keyword != None:
            start = 12*page
            sql = (
                "SELECT * FROM sight WHERE name LIKE (%s) OR category LIKE (%s) LIMIT %s,%s")
            val = (f"%{keyword}%", keyword, start, 13)
            mycursor.execute(sql, val)
            sightmeg = mycursor.fetchall()
            if sightmeg == []:
                return jsonify(error=True, message="無相關結果"), 500
            elif 12 < len(sightmeg):
                end = len(sightmeg)-1
                nextpage = page+1
            elif 12 >= len(sightmeg):
                end = len(sightmeg)
                nextpage = None
            for item in range(0, end):
                sql = (
                    "SELECT group_concat(image  separator ',' ) FROM images WHERE sight_id=(%s)")
                val = ([sightmeg[item][0]])
                mycursor.execute(sql, val)
                image = mycursor.fetchone()
                images = image[0].split(",")
                meg += {
                    "id": sightmeg[item][0],
                    "name": sightmeg[item][1],
                    "category": sightmeg[item][2],
                    "description": sightmeg[item][3],
                    "address": sightmeg[item][4],
                    "transport": sightmeg[item][5],
                    "mrt": sightmeg[item][6],
                    "lat": sightmeg[item][7],
                    "lng": sightmeg[item][8],
                    "images": images
                },
            return jsonify(nextpage=nextpage, data=meg)

        elif keyword == None:

            start = 12*page
            sql = ("SELECT * FROM sight LIMIT %s,%s")
            val = ([start, 13])
            mycursor.execute(sql, val)
            sightmeg = mycursor.fetchall()
            if 12 < len(sightmeg):
                end = len(sightmeg)-1
                nextpage = page+1
            elif 12 >= len(sightmeg):
                end = len(sightmeg)
                nextpage = None
            for item in range(0, end):
                sql = (
                    "SELECT group_concat(image  separator ',' ) FROM images WHERE sight_id=(%s)")
                val = ([sightmeg[item][0]])
                mycursor.execute(sql, val)
                image = mycursor.fetchone()
                images = image[0].split(",")
                meg += {
                    "id": sightmeg[item][0],
                    "name": sightmeg[item][1],
                    "category": sightmeg[item][2],
                    "description": sightmeg[item][3],
                    "address": sightmeg[item][4],
                    "transport": sightmeg[item][5],
                    "mrt": sightmeg[item][6],
                    "lat": sightmeg[item][7],
                    "lng": sightmeg[item][8],
                    "images": images
                },
            return jsonify(nextpage=nextpage, data=meg)

        else:
            return jsonify(error=True, message="oops!something wrong"), 500
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


@app.route("/api/attraction/<id>")
def attractionapi(id):
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor()
        sql = ("SELECT * FROM sight where id=(%s)")
        val = ([id])
        mycursor.execute(sql, val)
        sightmeg = mycursor.fetchone()
        if sightmeg == None:
            return jsonify(error=True, message="worng attraction number"), 400
        else:
            sql = (
                "SELECT group_concat(image  separator ',' ) FROM images WHERE sight_id=(%s)")
            val = ([id])
            mycursor.execute(sql, val)
            image = mycursor.fetchone()
            images = image[0].split(",")
            attraction = {
                "id": sightmeg[0],
                "name": sightmeg[1],
                "category": sightmeg[2],
                "description": sightmeg[3],
                "address": sightmeg[4],
                "transport": sightmeg[5],
                "mrt": sightmeg[6],
                "lat": sightmeg[7],
                "lng": sightmeg[8],
                "images": images
            }
            return jsonify(data=attraction)
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


@app.route("/api/categories")
def categories():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor()
        mycursor.execute(
            "SELECT group_concat(category  separator ',' ) FROM categories")
        category = mycursor.fetchone()
        categories = category[0].split(",")
        return jsonify(data=categories)
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


@app.route("/api/booking", methods=["GET", "POST", "DELETE"])
def apibooking():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor(buffered=True)
        try:
            auth = jwt.decode(request.cookies.get(
                'Set-Cookie'), 'secret', algorithms=['HS256'])
        except:
            response = jsonify(error=True, message="請先登入後再操作"), 403
            response.delete_cookie("Set-Cookie")
            return response
        if request.method == "GET":
            sql = "SELECT * FROM trip_order WHERE member_id = %s AND bill_id IS NULL"
            val = ([auth['id']])
            mycursor.execute(sql, val)
            bookingmeg = mycursor.fetchall()
            data = []
            for item in range(0, len(bookingmeg)):
                sql = "SELECT id,name,address,image FROM sight JOIN images ON sight_id=sight.id WHERE id= %s"
                val = ([bookingmeg[item][2]])
                mycursor.execute(sql, val)
                attractionmeg = mycursor.fetchone()
                data += {
                    "attraction": {
                        "id": attractionmeg[0],
                        "name": attractionmeg[1],
                        "address": attractionmeg[2],
                        "image": attractionmeg[3]
                    },
                    "date": bookingmeg[item][3],
                    "time": bookingmeg[item][4],
                    "price": bookingmeg[item][5],
                    "trip_id": bookingmeg[item][0]
                },
            return jsonify(data=data)
        elif request.method == "POST":
            sql = "INSERT INTO trip_order (member_id,sight_id,date,time,price) VALUES (%s, %s, %s, %s, %s)"
            val = (auth['id'], request.json.get("attractionId"), request.json.get(
                "date"), request.json.get("time"), request.json.get("price"))
            mycursor.execute(sql, val)
            mydb.commit()
            return jsonify(ok=True)
        elif request.method == "DELETE":
            sql = "DELETE FROM trip_order WHERE id = %s"
            val = ([request.json.get("id")])
            mycursor.execute(sql, val)
            mydb.commit()
            return jsonify(ok=True)
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


# member center APIs
@app.route("/api/member", methods=["GET", "PATCH", "POST"])
def memberapi():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor(buffered=True)
        try:
            auth = jwt.decode(request.cookies.get(
                'Set-Cookie'), 'secret', algorithms=['HS256'])
        except:
            response = jsonify(error=True, message="請先登入後再操作"), 403
            response.delete_cookie("Set-Cookie")
            return response
        if request.method == "GET":
            try:
                sql = "SELECT number,price,person,phone,contactemail FROM bills WHERE member_id =%s AND payment =1"
                val = [auth['id']]
                mycursor.execute(sql, val)
                membermeg = mycursor.fetchall()
                orders = []
                for item in range(0, len(membermeg)):
                    orders += {
                        "number": membermeg[item][0],
                        "price": membermeg[item][1],
                        "person": membermeg[item][2],
                        "phone": membermeg[item][3],
                        "email": membermeg[item][4]
                    },

                return jsonify(data={"orders": orders})
            except:
                return jsonify(error=True, message="您還沒有購買任何行程唷！")
        elif request.method == "PATCH":

            try:
                sql = "UPDATE member SET name= %s ,email= %s,phone = %s WHERE id = %s"
                val = [request.json.get("name"), request.json.get(
                    "email"), request.json.get("phone"), auth['id']]
                mycursor.execute(sql, val)
                mydb.commit()
            except:
                return jsonify(error=True, message="此信箱已被註冊"), 403
            sql = "SELECT * FROM member WHERE id = %s"
            val = [auth['id']]
            mycursor.execute(sql, val)
            authdata = mycursor.fetchone()
            response = jsonify(ok=True)
            auth = jwt.encode({
                "id": authdata[0],
                "name": authdata[1],
                "email": authdata[2],
                "phone": authdata[5],
                "pic": authdata[4]
            }, 'secret', algorithm='HS256')
            response.delete_cookie("Set-Cookie")
            response.set_cookie("Set-Cookie", value=auth, max_age=604800)
            return response
        elif request.method == "POST":
            file = request.files['file']
            filename = file.filename
            _, file_extension = os.path.splitext(filename)
            new_filename = str(auth['id']) + file_extension
            file.save(os.path.join('static/images', new_filename))
            sql = "UPDATE member SET pic= %s WHERE id = %s"
            val = [new_filename, auth['id']]
            mycursor.execute(sql, val)
            mydb.commit()
            sql = "SELECT * FROM member WHERE id = %s"
            val = [auth['id']]
            mycursor.execute(sql, val)
            authdata = mycursor.fetchone()
            response = jsonify(ok=True)
            auth = jwt.encode({
                "id": authdata[0],
                "name": authdata[1],
                "email": authdata[2],
                "phone": authdata[5],
                "pic": authdata[4]
            }, 'secret', algorithm='HS256')
            response.delete_cookie("Set-Cookie")
            response.set_cookie("Set-Cookie", value=auth, max_age=604800)
            return response
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


@app.route("/api/memberorder")
def memberorder():
    try:
        mydb = connection_pool.get_connection()
        mycursor = mydb.cursor(buffered=True)
        try:
            auth = jwt.decode(request.cookies.get(
                'Set-Cookie'), 'secret', algorithms=['HS256'])
        except:
            response = jsonify(error=True, message="請先登入後再操作"), 403
            response.delete_cookie("Set-Cookie")
            return response
        sql = "SELECT trip_order.date,trip_order.time,trip_order.price,trip_order.sight_id FROM trip_order JOIN bills ON bill_id=bills.id WHERE number = %s AND bill_id IS NOT NULL;"
        val = [request.args.get("number")]
        mycursor.execute(sql, val)
        bookingmeg = mycursor.fetchall()

        data = []
        for item in range(0, len(bookingmeg)):
            sql = "SELECT id,name,address,image FROM sight JOIN images ON sight_id=sight.id WHERE id= %s"
            val = ([bookingmeg[item][3]])
            mycursor.execute(sql, val)
            attractionmeg = mycursor.fetchone()

            data += {
                "attraction": {
                    "id": attractionmeg[0],
                    "name": attractionmeg[1],
                    "address": attractionmeg[2],
                    "image": attractionmeg[3]
                },
                "date": bookingmeg[item][0],
                "time": bookingmeg[item][1],
                "price": bookingmeg[item][2],
            },
        return jsonify(data=data)
    except:
        return jsonify(error=True, message="connection fail"), 500
    finally:
        mycursor.close()
        mydb.close()


app.debug = True
app.run(host="0.0.0.0", port=3000)
