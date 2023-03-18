import mysql.connector
import json

mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="newpassword",
    database="travel"
)

with open("taipei-attractions.json", mode="r", encoding="utf-8") as attractions:
    attraction = json.load(attractions)
    id = 0
    while id < len(attraction["result"]["results"]):
        mycursor = mydb.cursor()
        sql = "INSERT ignore INTO categories (category) VALUES (%s)"
        val = ([attraction["result"]["results"][id]["CAT"]])
        mycursor.execute(sql, val)
        mydb.commit()
        if attraction["result"]["results"][id]["MRT"] != None:
            sql = "INSERT ignore INTO mrts (mrt)  VALUES (%s)"
            val = ([attraction["result"]["results"][id]["MRT"]])
            mycursor.execute(sql, val)
            mydb.commit()
        sql = "INSERT INTO sight (name,description,address,transport,lat,lng,category,mrt) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        val = attraction["result"]["results"][id]["name"], attraction["result"]["results"][id]["description"], attraction["result"]["results"][id]["address"],attraction["result"]["results"][id]["direction"], attraction["result"]["results"][id]["latitude"], attraction["result"]["results"][id]["longitude"],attraction["result"]["results"][id]["CAT"],attraction["result"]["results"][id]["MRT"]   
        mycursor.execute(sql, val)
        mydb.commit()
        for image in attraction["result"]["results"][id]["file"].split("http"):
            image = "http"+image.lower()
            if "jpg" in image:
                sql = "INSERT INTO images(sight_id,image) VALUES (%s, %s)"
                val = id+1,image
                mycursor.execute(sql, val)
                mydb.commit()
        id += 1
