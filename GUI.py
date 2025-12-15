import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
from py2neo import Graph

NEO4J_IP = "44.204.255.88"
NEO4J_PORT = "7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "thunder-relief-classification"

try:
    graph = Graph(f"bolt://{NEO4J_IP}:{NEO4J_PORT}", auth=(NEO4J_USER, NEO4J_PASS))
    print("Berhasil terhubung ke Neo4j!")
except Exception as e:
    print(f"Gagal terhubung ke Neo4j: {e}")
    graph = None

MODEL_PATH = "airline-sentiment-model"
try:
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
except OSError:
    print(f"Model tidak ditemukan di path: {MODEL_PATH}. Pastikan folder sudah benar.")
    tokenizer = None
    model = None

label_map = {0: "Negative", 1: "Neutral", 2: "Positive"}

def save_to_neo4j(data_params):
    if graph is None:
        messagebox.showerror("Error", "Tidak terhubung ke Database Neo4j!")
        return

    cypher_query = """
    MERGE (p:Passenger {name: $name})
    MERGE (route:Route {name: $route})
    MERGE (ac:Aircraft {model: $aircraft})
    MERGE (st:SeatType {class: $seat_type})
    MERGE (tt:TravellerType {type: $traveller_type})

    CREATE (r:Review {
        date: $datetime,
        text: $review_text,
        verified: $verified,
        recommended: $recommended,
        date_flown: $date_flown,
        
        overall_rating: toFloat($overall_rating),
        seat_comfort: toFloat($seat_comfort),
        cabin_staff: toFloat($cabin_staff),
        ground_service: toFloat($ground_service),
        value_money: toFloat($value_money),
        food: toFloat($food),
        entertainment: toFloat($entertainment),
        wifi: toFloat($wifi)
    })

    MERGE (p)-[:WROTE]->(r)
    MERGE (r)-[:ABOUT_FLIGHT]->(route)
    MERGE (r)-[:FLOWN_ON]->(ac)
    MERGE (r)-[:IN_SEAT]->(st)
    MERGE (r)-[:TRAVELLED_AS]->(tt)

    MERGE (s:Sentiment {label: $sentiment})
    MERGE (r)-[:HAS_SENTIMENT]->(s)
    """

    try:
        graph.run(cypher_query, **data_params)
        print("Data berhasil disimpan ke Neo4j.")
        messagebox.showinfo("Sukses", "Sentimen diprediksi & Data disimpan ke Neo4j!")
    except Exception as e:
        print(f"Error Neo4j: {e}")
        messagebox.showerror("Error Database", f"Gagal menyimpan data: {e}")

def show_dashboard():
    if graph is None:
        messagebox.showerror("Error", "Tidak terhubung ke Database Neo4j!")
        return

    dash = tk.Toplevel(root)
    dash.title("Dashboard Analisis Data")
    dash.geometry("900x750")

    lbl_global = ttk.Label(dash, text="📊 Statistik Sentimen keseluruhan per Aspek", font=("Arial", 12, "bold"))
    lbl_global.pack(pady=(15, 5))

    frame_table = ttk.Frame(dash)
    frame_table.pack(fill="both", expand=True, padx=20, pady=5)

    cols = ("Aspect", "Category", "Count")
    tree = ttk.Treeview(frame_table, columns=cols, show="headings", height=10)
    
    tree.heading("Aspect", text="Aspek Layanan")
    tree.heading("Category", text="Sentimen")
    tree.heading("Count", text="Jumlah Review")
    
    tree.column("Aspect", width=200)
    tree.column("Category", width=150)
    tree.column("Count", width=100, anchor="center")
    
    scrollbar = ttk.Scrollbar(frame_table, orient="vertical", command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    ttk.Separator(dash, orient="horizontal").pack(fill="x", pady=10)
    
    lbl_individual = ttk.Label(dash, text="👤 Analisis Review Terakhir Masuk", font=("Arial", 12, "bold"))
    lbl_individual.pack(pady=(5, 10))

    frame_detail = ttk.LabelFrame(dash, text="Detail Penilaian", padding=15)
    frame_detail.pack(fill="x", padx=20, pady=5)
    
    content_frame = ttk.Frame(frame_detail)
    content_frame.pack(fill="x")

    def load_data():
        for item in tree.get_children():
            tree.delete(item)
        for widget in content_frame.winfo_children():
            widget.destroy()

        query_global = """
        MATCH (r:Review)
        UNWIND ['seat_comfort', 'cabin_staff', 'ground_service', 'value_money', 'food', 'entertainment', 'wifi'] AS aspect
        WITH aspect, r[aspect] AS score
        WHERE score >= 0
        WITH aspect, score,
             CASE
               WHEN score >= 4 THEN 'Positive'
               WHEN score >= 2 THEN 'Neutral'
               ELSE 'Negative'
             END AS sentiment_category
        RETURN aspect, sentiment_category, count(score) AS total_reviews
        ORDER BY aspect, sentiment_category
        """
        try:
            data_global = graph.run(query_global).data()
            for row in data_global:
                tree.insert("", "end", values=(
                    row['aspect'].replace("_", " ").title(), 
                    row['sentiment_category'], 
                    row['total_reviews']
                ))
        except Exception as e:
            print(f"Error Global: {e}")

        query_individual = """
        MATCH (r:Review)
        ORDER BY id(r) DESC 
        LIMIT 1
        RETURN 
            r.name AS PassengerName,
            r.seat_comfort AS seat_comfort,
            r.cabin_staff AS cabin_staff,
            r.food AS food,
            r.wifi AS wifi,
            r.entertainment AS entertainment,
            r.ground_service AS ground_service,
            r.value_money AS value_money
        """
        try:
            result_ind = graph.run(query_individual).data()
            if result_ind:
                data = result_ind[0]
                ttk.Label(content_frame, text=f"Nama Penumpang: {data.get('PassengerName', 'Unknown')}", font=("Arial", 11, "bold")).grid(row=0, column=0, sticky="w", columnspan=3, pady=(0, 10))

                def get_status(score):
                    if score is None: score = -1.0
                    
                    if score < 0: return "N/A (Invalid)", "gray"
                    elif score >= 4: return "Positive", "green"
                    elif score >= 2: return "Neutral", "#cfb102" 
                    else: return "Negative", "red" 
                aspects_to_show = [
                    ("Seat Comfort", data.get('seat_comfort')),
                    ("Cabin Staff", data.get('cabin_staff')),
                    ("Food & Bev", data.get('food')),
                    ("Wifi", data.get('wifi')),
                    ("Entertainment", data.get('entertainment')),
                    ("Ground Service", data.get('ground_service')),
                    ("Value Money", data.get('value_money'))
                ]

                for i, (label_text, score) in enumerate(aspects_to_show):
                    score = float(score) if score is not None else -1.0
                    status_text, color = get_status(score)
                    
                    ttk.Label(content_frame, text=label_text + ":").grid(row=i+1, column=0, sticky="w", padx=5, pady=2)
                    
                    pb_val = score if score >= 0 else 0
                    pb = ttk.Progressbar(content_frame, orient="horizontal", length=200, mode="determinate", maximum=5)
                    pb['value'] = pb_val
                    pb.grid(row=i+1, column=1, padx=10, pady=2)
                    
                    lbl_stat = tk.Label(content_frame, text=f"{score} ({status_text})", fg=color)
                    lbl_stat.grid(row=i+1, column=2, sticky="w", padx=5)
            else:
                ttk.Label(content_frame, text="Belum ada data.").pack()
        except Exception as e:
            print(f"Error Individual: {e}")

    btn_frame = ttk.Frame(dash)
    btn_frame.pack(pady=20)
    
    ttk.Button(btn_frame, text="🔄 Refresh Data", command=load_data).pack(side="left", padx=10)
    ttk.Button(btn_frame, text="Tutup Dashboard", command=dash.destroy).pack(side="left", padx=10)
    load_data()

def predict_and_save():
    review_text = review_input.get("1.0", tk.END).strip()

    if not review_text:
        sentiment_var.set("Please enter text")
        return
    
    if model is None:
        sentiment_var.set("Model Error")
        return

    try:
        inputs = tokenizer(review_text, return_tensors="pt", truncation=True, padding=True)
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits
            pred_id = torch.argmax(logits, dim=1).item()

        sentiment_result = label_map[pred_id]
        sentiment_var.set(sentiment_result)
        
        def get_val(key, default="-1"): 
            val = entries[key].get().strip()
            return val if val else default

        params = {
            "name": get_val("Name", "Anonymous"),
            "route": get_val("Route", "Unknown Route"),
            "aircraft": get_val("Aircraft", "Unknown Aircraft"),
            "seat_type": get_val("SeatType", "Unknown Class"),
            "traveller_type": get_val("TypeOfTraveller", "Unknown Type"),
            "datetime": get_val("Datetime"),
            "review_text": review_text,
            "verified": get_val("VerifiedReview", "False"),
            "recommended": get_val("Recommended", "no"),
            "date_flown": get_val("DateFlown"),
            "overall_rating": get_val("OverallRating"),
            "seat_comfort": get_val("SeatComfort"),
            "cabin_staff": get_val("CabinStaffService"),
            "ground_service": get_val("GroundService"),
            "value_money": get_val("ValueForMoney"),
            "food": get_val("Food & Beverages"),
            "entertainment": get_val("Inflight Entertainment"),
            "wifi": get_val("Wifi & Connectivity"),
            
            "sentiment": sentiment_result
        }

        save_to_neo4j(params)

    except Exception as e:
        sentiment_var.set("Error")
        print(f"Error processing: {e}")
        messagebox.showerror("Error", str(e))

root = tk.Tk()
root.title("Airline Review Sentiment Classifier + Neo4j")
root.geometry("750x700") 

main_frame = ttk.Frame(root, padding=20)
main_frame.pack(fill="both", expand=True)

main_frame.columnconfigure(1, weight=1) 
main_frame.columnconfigure(3, weight=1)

fields = [
    "OverallRating",         
    "Name",                    
    "Datetime",                
    "VerifiedReview",        
    "TypeOfTraveller",        
    "SeatType",                
    "Route",                   
    "DateFlown",             
    "SeatComfort",             
    "CabinStaffService",       
    "GroundService",           
    "ValueForMoney",           
    "Recommended",             
    "Aircraft",               
    "Food & Beverages",        
    "Inflight Entertainment",  
    "Wifi & Connectivity"      
]

entries = {}

for i, field in enumerate(fields):
    row_pos = i // 2
    col_pos = (i % 2) * 2
    
    label = ttk.Label(main_frame, text=field + ":")
    label.grid(row=row_pos, column=col_pos, sticky="w", pady=5, padx=(0, 10))

    entry = ttk.Entry(main_frame)
    entry.grid(row=row_pos, column=col_pos + 1, pady=5, padx=(0, 20), sticky="ew")
    entries[field] = entry

last_row = (len(fields) // 2) + 1

review_label = ttk.Label(main_frame, text="Review Text:")
review_label.grid(row=last_row, column=0, sticky="nw", pady=(20,5))

review_input = scrolledtext.ScrolledText(main_frame, height=6)
review_input.grid(row=last_row + 1, column=0, columnspan=4, pady=5, sticky="ew")

predict_button = ttk.Button(main_frame, text="Prediksi Sentimen & Simpan", command=predict_and_save)
predict_button.grid(row=last_row + 2, column=0, columnspan=4, pady=(20, 10), sticky="ew", ipady=5)

dashboard_button = ttk.Button(main_frame, text="📊 Lihat Dashboard Analisis Data", command=show_dashboard)
dashboard_button.grid(row=last_row + 3, column=0, columnspan=4, pady=5, sticky="ew", ipady=5)

sentiment_var = tk.StringVar()
sentiment_var.set("-")

sentiment_container = ttk.Frame(main_frame)
sentiment_container.grid(row=last_row + 4, column=0, columnspan=4, pady=10)

sentiment_label = ttk.Label(sentiment_container, text="Sentiment: ")
sentiment_label.pack(side="left")

sentiment_output = ttk.Label(sentiment_container, textvariable=sentiment_var, font=("Arial", 16, "bold"), foreground="blue")
sentiment_output.pack(side="left")

exit_button = ttk.Button(main_frame, text="Exit", command=root.destroy)
exit_button.grid(row=last_row + 5, column=0, columnspan=4, pady=10, sticky="ew")

root.mainloop()
