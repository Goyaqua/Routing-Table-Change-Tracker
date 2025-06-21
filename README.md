# 🛰️ Routing Table Change Tracker

A Python-based CLI tool for **real-time tracking and visualization of routing table changes**.

It logs added/removed routes, saves structured logs to `.csv` and `.log` files, and draws interactive network topology graphs using `matplotlib` and `networkx`.

---

## 📦 Features

- ✅ Real-time monitoring using `ip route`
- ✅ Detects added and removed routes
- ✅ Logs changes to `.log` and `.csv` with timestamps
- ✅ Visualizes routes as dynamic topology graphs
- ✅ CLI with customizable interval, output folder, file prefix
- ✅ Test mode with mock routing data
- ✅ Graceful shutdown with `Ctrl+C`

---

## 🖥️ Requirements

- Python 3.6+
- Linux or macOS (must support `ip route`)
- Python packages:
  ```bash
  pip install -r requirements.txt
``

---

## 🚀 Usage

### 📡 Live Monitoring

```bash
python route_tracker.py
```

### ⏱ Custom Interval, Output Directory & File Prefix

```bash
python route_tracker.py --interval 5 --output-dir logs --prefix office_router
```

### 📴 Disable Console Output (for background jobs)

```bash
python route_tracker.py --no-console --interval 30
```

### 🧪 Test Mode (uses mock data, no `ip` command)

```bash
python route_tracker.py --test --output-dir test_logs --prefix test_run
```

---

## 🌐 Topology Visualization

Each route is visualized as a node. Connections show:

* **`this-host` → gateway** (🟨 Yellow)
* **Gateway or direct routes → destinations** (🟩 Green)
* **Intermediate next hops** (🟧 Orange)

The graph is redrawn after every routing table change. It uses **directed arrows** to show the direction of data flow.

---

## 🧪 Example Test Mode Output

You can test the tool without using `ip route` by running:

```bash
python route_tracker.py --test
```

This will:

* Use sample route tables
* Show changes
* Save them to CSV/log
* Render a topology graph

---
