import requests
from bs4 import BeautifulSoup

import firebase_admin
from firebase_admin import credentials, firestore
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

from flask import Flask, render_template, request, json, make_response, jsonify
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

@app.route("/")
def index():
    homepage = "<h1>楊子青Python網頁(Firestore) 電影分級查詢1</h1>"
    homepage += "<a href=/mis>MIS</a><br>"
    homepage += "<a href=/today>顯示日期時間</a><br>"
    homepage += "<a href=/welcome?nick=tcyang&work=pu>傳送使用者暱稱</a><br>"
    homepage += "<a href=/account>網頁表單傳值</a><br>"
    homepage += "<a href=/about>子青簡介網頁</a><br>"
    homepage += "<br><a href=/read>讀取Firestore資料</a><br>"
    homepage += "<a href=/read_keyword>根據關鍵字,查詢教師資料</a><br>"
    homepage += "<br><a href=/spider>擷取開眼即將上映電影,存到資料庫</a><br><br>"
    homepage += "<a href=/searchQ>輸入關鍵字查詢電影</a><br>"
    homepage += "<a href=/searchR>輸入關鍵字查詢114年1月台中十大易肇事路口</a><br>"
    homepage += "<a href=/searchR2>輸入關鍵字查詢114年1月台中十大易肇事路口(顯示在同一網頁)</a><br><br>"
    homepage += "<br><a href=/rate>擷取開眼即將上映電影(含分級及最新更新日期),存到資料庫</a><br>"

    return homepage


@app.route("/mis")
def course():
    return "<h1>資訊管理導論</h1>"


@app.route("/today")
def today():
    tz = timezone(timedelta(hours=+8))
    now = datetime.now(tz)
    return render_template("today.html", datetime = str(now))

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/welcome", methods=["GET"])
def welcome():
    user = request.values.get("nick")
    w = request.values.get("work")
    return render_template("welcome.html", name=user, work=w)


@app.route("/account", methods=["GET", "POST"])
def account():
    if request.method == "POST":
        user = request.form["user"]
        pwd = request.form["pwd"]
        result = "您輸入的帳號是：" + user + "; 密碼為：" + pwd 
        return result
    else:
        return render_template("account.html")


@app.route("/read")
def read():
    Result = ""
    db = firestore.client()
    collection_ref = db.collection("靜宜資管")    
    docs = collection_ref.order_by("mail").get()    
    for doc in docs:         
        Result += "文件內容：{}".format(doc.to_dict()) + "<br>"    
    return Result

@app.route("/read_keyword", methods=["GET", "POST"])
def read_keyword():
    if request.method == "POST":
        db = firestore.client()
        collection_ref = db.collection("靜宜資管")
        docs = collection_ref.order_by("lab").get()

        Result = ""
        x = request.form["user"]
        for doc in docs:
            result = doc.to_dict()
            if x in result["name"]:
                Result += "姓名:" + result["name"] + "; "
                Result += "郵件:" + result["mail"] + "; "
                Result += "研究室:" + str(result["lab"]) + "<br>"
        return Result
    else:
        return render_template("keyword.html")


@app.route("/spider")
def spider():
    db = firestore.client()

    url = "http://www.atmovies.com.tw/movie/next/"
    Data = requests.get(url)
    Data.encoding = "utf-8"

    sp = BeautifulSoup(Data.text, "html.parser")
    result=sp.select(".filmListAllX li")
    for item in result:
        i = item.find("img")
        a = item.find("a")

        r = item.find(class_= "runtime")

        pos = r.text.find("片長")
        pos2 = r.text.find("分")
        movieL = "無"
        if (pos>0):
            movieL = r.text[pos+3 : pos2 + 1]

        doc = {
            "title": i.get("alt"),
            "picture": i.get("src"),
            "hyperlink": "http://www.atmovies.com.tw" + a.get("href"), 
            "showDate": r.text[5:15],
            "showLength": movieL
        }
        id = a.get("href")[7:19]
     
        doc_ref = db.collection("電影").document(id)
        doc_ref.set(doc)
    return "電影資料庫更新"


@app.route("/search")
def search():
    info = ""
    db = firestore.client()  
    docs = db.collection("電影").get() 
    for doc in docs:
        if "" in doc.to_dict()["title"]:
            info += "片名：<a href=" + doc.to_dict()["hyperlink"] + ">" + doc.to_dict()["title"] + "</a><br>" 
            info += "海報：<img src=" + doc.to_dict()["picture"] + "> </img><br>"
            info += "片長：" + doc.to_dict()["showLength"] + "<br>" 
            info += "上映日期：" + doc.to_dict()["showDate"] + "<br><br>"           
    return info

@app.route("/searchQ", methods=["POST","GET"])
def searchQ():
    if request.method == "POST":
        MovieTitle = request.form["MovieTitle"]
        info = ""
        db = firestore.client()     
        collection_ref = db.collection("電影")
        docs = collection_ref.order_by("showDate").get()
        for doc in docs:
            if MovieTitle in doc.to_dict()["title"]: 
                info += "片名：<a href=" + doc.to_dict()["hyperlink"] + ">" + doc.to_dict()["title"] + "</a><br>" 
                info += "海報：<img src=" + doc.to_dict()["picture"] + "> </img><br>"
                info += "片長：" + doc.to_dict()["showLength"] + "<br>" 
                info += "上映日期：" + doc.to_dict()["showDate"] + "<br><br>"           
        return info
    else:  
        return render_template("input.html")

@app.route("/searchR", methods=["POST","GET"])
def searchR():
    if request.method == "POST":
        x = request.form["Road"]
        info = ""

        url = "https://datacenter.taichung.gov.tw/swagger/OpenData/b9c9b28d-847c-489d-ba60-94f8728910b9"
        Data = requests.get(url)
        #print(Data.text)

        JsonData = json.loads(Data.text)
        for item in JsonData:
            if x in item["路口名稱"]:
                info += "路口名稱：" + item["路口名稱"] + "<br>"
                info += "總件數：" + item["總件數"] + "<br>"
                info += "主要肇因：" + item["主要肇因"] + "<br><br>"         
        return info
    else:  
        return render_template("traffic.html")


@app.route("/searchR2", methods=["POST","GET"])
def searchR2():
    info = []
    if request.method == "POST":
        x = request.form["Road"]

        url = "https://datacenter.taichung.gov.tw/swagger/OpenData/b9c9b28d-847c-489d-ba60-94f8728910b9"
        Data = requests.get(url)
        #print(Data.text)

        JsonData = json.loads(Data.text)
        for item in JsonData:
            if x in item["路口名稱"]:
                info.append(
                    {

                        "路口名稱" : item["路口名稱"],
                        "總件數" : item["總件數"],
                        "主要肇因" : item["主要肇因"]
                    }
                )    
 
    return render_template("traffic.html", result=info)



@app.route("/rate")
def rate():
    url = "http://www.atmovies.com.tw/movie/next/"
    Data = requests.get(url)
    Data.encoding = "utf-8"
    sp = BeautifulSoup(Data.text, "html.parser")
    result=sp.select(".filmListAllX li")
    lastUpdate = sp.find(class_="smaller09").text[5:]

    for x in result:
        picture = x.find("img").get("src").replace(" ", "")
        title = x.find("img").get("alt")    
        movie_id = x.find("div", class_="filmtitle").find("a").get("href").replace("/", "").replace("movie", "")
        hyperlink = "http://www.atmovies.com.tw" + x.find("a").get("href")

        t = x.find(class_="runtime").text
        showDate = t[5:15]

        showLength = ""
        if "片長" in t:
            t1 = t.find("片長")
            t2 = t.find("分")
            showLength = t[t1+3:t2]

        r = x.find(class_="runtime").find("img")
        rate = ""
        if r != None:
            rr = r.get("src").replace("/images/cer_", "").replace(".gif", "")
            if rr == "G":
                rate = "普遍級"
            elif rr == "P":
                rate = "保護級"
            elif rr == "F2":
                rate = "輔12級"
            elif rr == "F5":
                rate = "輔15級"
            else:
                rate = "限制級"

        doc = {
            "title": title,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": showDate,
            "showLength": showLength,
            "rate": rate,
            "lastUpdate": lastUpdate
        }

        db = firestore.client()
        doc_ref = db.collection("電影含分級").document(movie_id)
        doc_ref.set(doc)
    return "近期上映電影已爬蟲及存檔完畢，網站最近更新日期為：" + lastUpdate



@app.route("/webhook_tcyang", methods=["POST"])
def webhook_tcyang():
    req = request.get_json(force=True)
    # fetch queryResult from json
    action =  req.get("queryResult").get("action")
    #msg =  req.get("queryResult").get("queryText")
    #info = "動作：" + action + "； 查詢內容：" + msg

    if (action == "rateChoice"):
        rate =  req.get("queryResult").get("parameters").get("rate")
        info = "您選擇的電影分級是：" + rate + "，相關電影：\n"
        db = firestore.client()
        collection_ref = db.collection("電影含分級")
        docs = collection_ref.get()
        result = ""
        for doc in docs:
            dict = doc.to_dict()
            if rate in dict["rate"]:
                result += "片名：" + dict["title"] + "\n"
                result += "介紹：" + dict["hyperlink"] + "\n\n"
        if result == "":
            result = "抱歉,資料庫目前無您要查詢分級的電影"
        info += result

    elif (action == "CityWeather"):
        city =  req.get("queryResult").get("parameters").get("city")
        token = "rdec-key-123-45678-011121314"
        url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-C0032-001?Authorization=" + token + "&format=JSON&locationName=" + str(city)
        Data = requests.get(url)
        Weather = json.loads(Data.text)["records"]["location"][0]["weatherElement"][0]["time"][0]["parameter"]["parameterName"]
        Rain = json.loads(Data.text)["records"]["location"][0]["weatherElement"][1]["time"][0]["parameter"]["parameterName"]
        MinT = json.loads(Data.text)["records"]["location"][0]["weatherElement"][2]["time"][0]["parameter"]["parameterName"]
        MaxT = json.loads(Data.text)["records"]["location"][0]["weatherElement"][4]["time"][0]["parameter"]["parameterName"]
        info = city + "的天氣是" + Weather + "，降雨機率：" + Rain + "%"
        info += "，溫度：" + MinT + "-" + MaxT + "度"

    return make_response(jsonify({"fulfillmentText": "這是楊子青的程式回覆," + info}))


@app.route("/webhook", methods=["POST"])
def webhook():
    req = request.get_json(force=True)
    # fetch queryResult from json
    action =  req.get("queryResult").get("action")
    #msg =  req.get("queryResult").get("queryText")
    #info = "動作：" + action + "； 查詢內容：" + msg

    if (action == "rateChoice"):
        rate =  req.get("queryResult").get("parameters").get("rate")
        info = "您選擇的電影分級是：" + rate + "，相關電影：\n"
        db = firestore.client()
        collection_ref = db.collection("電影含分級")
        docs = collection_ref.get()
        result = ""
        for doc in docs:
            dict = doc.to_dict()
            if rate in dict["rate"]:
                result += "片名：" + dict["title"] + "\n"
                result += "介紹：" + dict["hyperlink"] + "\n\n"
        if result == "":
            result = "抱歉,資料庫目前無您要查詢分級的電影"
        info += result

    return make_response(jsonify({"fulfillmentText": "這是楊子青的程式回覆," + info}))

if __name__ == "__main__":
    app.run(debug=True)
