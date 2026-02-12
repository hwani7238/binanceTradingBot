import tkinter as tk
from tkinter import ttk
import threading
import time
import sys
import os

# Ensure src is in path to import main correctly if run from project root
sys.path.append(os.getcwd())

from src.main import TradingBot

class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Binance AI Trading Bot")
        self.root.geometry("400x450")
        
        # Initialize Bot (Model loading might take a moment)
        self.bot = TradingBot()
        
        # Styles
        style = ttk.Style()
        style.configure("TLabel", font=("Helvetica", 12))
        style.configure("TButton", font=("Helvetica", 12))
        
        # Main Frame
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(main_frame, text="AI Trading Bot Control", font=("Helvetica", 16, "bold"))
        header.pack(pady=10)
        
        # Status Section
        self.status_var = tk.StringVar(value="Status: STOPPED")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="red")
        self.status_label.pack(pady=5)
        
        # Info Grid
        info_frame = ttk.LabelFrame(main_frame, text="Live Statistics", padding="10")
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Helper to create rows
        def create_row(parent, label, var, row):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
            lbl = ttk.Label(parent, textvariable=var, font=("Helvetica", 12, "bold"))
            lbl.grid(row=row, column=1, sticky="e", pady=5)
            return lbl

        self.price_var = tk.StringVar(value="--")
        create_row(info_frame, "Price (BTC):", self.price_var, 0)
        
        self.balance_var = tk.StringVar(value="--")
        create_row(info_frame, "Balance (USDT):", self.balance_var, 1)
        
        self.pos_var = tk.StringVar(value="--")
        create_row(info_frame, "Position:", self.pos_var, 2)
        
        self.pnl_var = tk.StringVar(value="--")
        self.pnl_label = create_row(info_frame, "Est. PnL:", self.pnl_var, 3)
        
        self.action_var = tk.StringVar(value="--")
        create_row(info_frame, "Last Action:", self.action_var, 4)

        # Controls
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        
        self.start_btn = ttk.Button(btn_frame, text="START BOT", command=self.start_bot)
        self.start_btn.pack(side=tk.LEFT, padx=10)
        
        self.stop_btn = ttk.Button(btn_frame, text="STOP BOT", command=self.stop_bot, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=10)
        
        # Update Loop
        self.update_ui()

    def start_bot(self):
        self.bot.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_var.set("Status: RUNNING")
        self.status_label.config(foreground="green")

    def stop_bot(self):
        self.bot.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Status: STOPPING...")
        self.status_label.config(foreground="orange")

    def update_ui(self):
        # Poll bot status
        status = self.bot.get_status()
        
        if status['price'] > 0:
            self.price_var.set(f"{status['price']:.2f}")
        
        self.balance_var.set(f"{status['balance']:.2f}")
        
        pos = status['position']
        pos_text = "NONE"
        if pos == 1: pos_text = "LONG"
        elif pos == -1: pos_text = "SHORT"
        self.pos_var.set(pos_text)
        
        pnl = status['unrealized_pnl']
        self.pnl_var.set(f"{pnl:.2f}")
        if pnl > 0:
            self.pnl_label.config(foreground="green")
        elif pnl < 0:
            self.pnl_label.config(foreground="red")
        else:
            self.pnl_label.config(foreground="black")
            
        self.action_var.set(status['action'])
        
        # Sync Running State
        if status['running']:
            self.status_var.set(f"Status: RUNNING ({status['last_update']})")
            self.status_label.config(foreground="green")
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
        else:
            if self.status_var.get().startswith("Status: RUNNING"):
               self.status_var.set("Status: STOPPED")
               self.status_label.config(foreground="red")
               self.start_btn.config(state=tk.NORMAL)
               self.stop_btn.config(state=tk.DISABLED)
        
        self.root.after(1000, self.update_ui)

if __name__ == "__main__":
    root = tk.Tk()
    app = TradingBotGUI(root)
    root.mainloop()
