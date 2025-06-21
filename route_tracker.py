import subprocess
import time
import csv
import logging
from datetime import datetime
import networkx as nx
import matplotlib.pyplot as plt
import re
import os
import argparse

class RouteTracker:
    def __init__(self, output_dir='.', log_to_console=True, file_prefix=None):
        """Initialize the route tracker.
        
        Args:
            output_dir (str): Directory for log and CSV files
            log_to_console (bool): Whether to print updates to console
            file_prefix (str): Optional prefix for log and CSV filenames
        """
        self.output_dir = output_dir
        self.log_to_console = log_to_console
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate timestamp for file names
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix = f"{file_prefix}_" if file_prefix else ""
        
        # Set up file paths
        self.log_file = os.path.join(output_dir, f'{prefix}routing_changes_{timestamp}.log')
        self.csv_file = os.path.join(output_dir, f'{prefix}routing_changes_{timestamp}.csv')
        
        # Configure logging
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
        
        # Set up console logging if enabled
        if log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            logging.getLogger().addHandler(console_handler)
        
        if self.log_to_console:
            print(f"Log file: {self.log_file}")
            print(f"CSV file: {self.csv_file}")
    
    def get_current_routes(self):
        """Run the 'ip route' command and return the output."""
        try:
            result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
            return result.stdout.splitlines()
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running 'ip route': {e}")
            return []

    def parse_routes(self, output):
        """Parse the routing table output into a set of routes with metrics."""
        routes = {}
        gateway = None
        for line in output:
            # Extract default gateway
            if line.startswith("default"):
                match = re.search(r'default via (\S+)', line)
                if match:
                    gateway = match.group(1)
                    continue
            
            # Extract routes with next hop (via)
            match = re.search(r'(\S+)\s+via\s+(\S+)', line)
            if match:
                destination = match.group(1)
                next_hop = match.group(2)
                routes[destination] = (None, None, next_hop)
            else:
                # Directly connected routes (no via)
                parts = line.split()
                if len(parts) >= 1:
                    destination = parts[0]
                    if destination != "default":  # Skip default route as it's handled above
                        routes[destination] = (None, None, "direct")
        
        return routes, gateway

    def compare_routes(self, before, after):
        """Compare two sets of routes and return added and removed routes with metrics."""
        added = {route: after[route] for route in after if route not in before}
        removed = {route: before[route] for route in before if route not in after}
        return added, removed

    def log_changes(self, added, removed):
        """Log the changes with timestamps."""
        if added:
            logging.info(f"Added routes: {', '.join(added.keys())} with metrics: {', '.join(str(v) for v in added.values())}")
        if removed:
            logging.info(f"Removed routes: {', '.join(removed.keys())} with metrics: {', '.join(str(v) for v in removed.values())}")

    def save_to_csv(self, added, removed):
        """Save the changes to a CSV file."""
        file_exists = os.path.isfile(self.csv_file) and os.path.getsize(self.csv_file) > 0

        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            if not file_exists:
                writer.writerow(['Change Type', 'Route', 'Admin Distance', 'Metric', 'Next Hop', 'Timestamp'])
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for route, (admin_distance, metric, next_hop) in added.items():
                writer.writerow(['Added', route, admin_distance, metric, next_hop, timestamp])
            for route, (admin_distance, metric, next_hop) in removed.items():
                writer.writerow(['Removed', route, admin_distance, metric, next_hop, timestamp])

    def create_topology_graph(self, routes, gateway):
        """Create a topology graph of the routes."""
        G = nx.DiGraph()
        
        # Add nodes
        host_node = "this-host"
        G.add_node(host_node, color='lightblue')
        
        if gateway:
            G.add_node(gateway, color='yellow')
            G.add_edge(host_node, gateway)
        
        # Add routes and their connections
        for destination, (_, _, next_hop) in routes.items():
            G.add_node(destination, color='green')
            
            if next_hop == "direct":
                G.add_edge(host_node, destination)
            else:
                # If it's via a gateway, connect through the gateway
                if gateway and next_hop == gateway:
                    G.add_edge(gateway, destination)
                else:
                    # If it's via another hop, add that hop
                    G.add_node(next_hop, color='orange')
                    G.add_edge(gateway if gateway else host_node, next_hop)
                    G.add_edge(next_hop, destination)

        # Set up the layout
        pos = nx.spring_layout(G)
        
        # Draw the graph
        plt.figure(figsize=(12, 8))
        
        # Draw nodes with different colors
        node_colors = [G.nodes[node]['color'] for node in G.nodes()]
        nx.draw_networkx_nodes(G, pos, node_color=node_colors)
        
        # Draw edges with arrows
        nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True)
        
        # Draw labels
        nx.draw_networkx_labels(G, pos)
        
        plt.title("Network Topology")
        plt.axis('off')
        plt.show()

    def print_route_summary(self, routes, gateway):
        """Print a summary of the current routing table."""
        if not self.log_to_console:
            return
            
        direct_routes = sum(1 for _, (_, _, next_hop) in routes.items() if next_hop == "direct")
        gateway_routes = sum(1 for _, (_, _, next_hop) in routes.items() if next_hop != "direct")
        
        print("\nRoute Summary:")
        print(f"Total Routes: {len(routes)}")
        print(f"├─ Direct Routes: {direct_routes}")
        print(f"└─ Gateway Routes: {gateway_routes}")
        if gateway:
            print(f"Default Gateway: {gateway}")
        print("-" * 40)

    def monitor(self, interval=10):
        """Monitor the routing table for changes."""
        if self.log_to_console:
            print(f"Starting route monitoring (checking every {interval} seconds)...")
            print("Press Ctrl+C to stop monitoring.")
        
        # Get initial routing table
        initial_output = self.get_current_routes()
        previous_routes, previous_gateway = self.parse_routes(initial_output)
        
        # Print initial summary
        self.print_route_summary(previous_routes, previous_gateway)
        
        try:
            while True:
                time.sleep(interval)
                
                # Get current routing table
                current_output = self.get_current_routes()
                current_routes, current_gateway = self.parse_routes(current_output)
                
                # Compare and process changes
                added, removed = self.compare_routes(previous_routes, current_routes)
                
                if added or removed:
                    if self.log_to_console:
                        print("\nRouting changes detected!")
                        if added:
                            print("Added routes:", ", ".join(added.keys()))
                        if removed:
                            print("Removed routes:", ", ".join(removed.keys()))
                    
                    # Log and save changes
                    self.log_changes(added, removed)
                    self.save_to_csv(added, removed)
                    
                    # Print updated summary
                    self.print_route_summary(current_routes, current_gateway)
                    
                    # Update topology graph
                    if self.log_to_console:
                        print("Updating topology graph...")
                    self.create_topology_graph(current_routes, current_gateway)
                    
                    # Update previous routes for next comparison
                    previous_routes = current_routes
                    previous_gateway = current_gateway
                
        except KeyboardInterrupt:
            if self.log_to_console:
                print("\nMonitoring stopped.")

def run_test(output_dir='.', log_to_console=True, file_prefix=None):
    """Run the route tracker in test mode with mock data."""
    tracker = RouteTracker(output_dir=output_dir, log_to_console=log_to_console, file_prefix=file_prefix)
    
    # Mock route tables for testing
    before_routes = """
default via 192.168.1.1 dev eth0
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100
172.16.0.0/16 via 192.168.1.1 dev eth0
10.0.0.0/8 via 192.168.1.1 dev eth0
""".strip().split('\n')

    after_routes = """
default via 192.168.1.1 dev eth0
192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100
172.16.0.0/16 via 192.168.1.1 dev eth0
10.0.0.0/8 via 192.168.1.2 dev eth0
192.168.2.0/24 via 192.168.1.1 dev eth0
""".strip().split('\n')

    if log_to_console:
        print("Running in test mode with mock route tables...")
    
    # Process before routes
    previous_routes, previous_gateway = tracker.parse_routes(before_routes)
    
    # Print initial summary
    tracker.print_route_summary(previous_routes, previous_gateway)
    
    # Process after routes
    current_routes, current_gateway = tracker.parse_routes(after_routes)
    
    # Compare and process changes
    added, removed = tracker.compare_routes(previous_routes, current_routes)
    
    if added or removed:
        if log_to_console:
            print("\nRouting changes detected!")
            if added:
                print("Added routes:", ", ".join(added.keys()))
            if removed:
                print("Removed routes:", ", ".join(removed.keys()))
        
        # Log and save changes
        tracker.log_changes(added, removed)
        tracker.save_to_csv(added, removed)
        
        # Print updated summary
        tracker.print_route_summary(current_routes, current_gateway)
        
        # Update topology graph
        if log_to_console:
            print("Creating topology graph...")
        tracker.create_topology_graph(current_routes, current_gateway)
    
    if log_to_console:
        print("\nTest completed.")
    return True

def run_tracker(interval=10, output_dir='.', log_to_console=True, file_prefix=None):
    """Run the route tracker with specified parameters."""
    tracker = RouteTracker(output_dir=output_dir, log_to_console=log_to_console, file_prefix=file_prefix)
    tracker.monitor(interval=interval)

def main():
    parser = argparse.ArgumentParser(description='Monitor routing table changes.')
    parser.add_argument('-i', '--interval', 
                      type=int, 
                      default=10,
                      help='Monitoring interval in seconds (default: 10)')
    parser.add_argument('-o', '--output-dir',
                      type=str,
                      default='.',
                      help='Directory for log and CSV files (default: current directory)')
    parser.add_argument('--no-console',
                      action='store_true',
                      help='Disable console output')
    parser.add_argument('-p', '--prefix',
                      type=str,
                      default=None,
                      help='Prefix for log and CSV filenames')
    parser.add_argument('-t', '--test',
                      action='store_true',
                      help='Run in test mode with mock route tables')
    
    args = parser.parse_args()
    
    if args.interval < 1:
        print("Error: Interval must be at least 1 second")
        return
    
    if args.test:
        run_test(
            output_dir=args.output_dir,
            log_to_console=not args.no_console,
            file_prefix=args.prefix
        )
    else:
        run_tracker(
            interval=args.interval,
            output_dir=args.output_dir,
            log_to_console=not args.no_console,
            file_prefix=args.prefix
        )

if __name__ == "__main__":
    main()
