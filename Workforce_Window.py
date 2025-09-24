import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import StringVar
import pandas as pd

class BreakdownJobsPopup:
    def __init__(self, parent, job_breakdown_callback):
        self.parent = parent
        self.job_breakdown_callback = job_breakdown_callback
        self.breakdown_jobs_window = tk.Toplevel(self.parent)
        self.breakdown_jobs_window.title("Break Down Jobs")
        self.breakdown_jobs_window.geometry("800x600")

        # Entry and Browse button for Excel file path
        ttk.Label(self.breakdown_jobs_window, text="Excel File Path:").grid(column=0, row=0, padx=5, pady=5, sticky="w")
        self.file_path_var = StringVar()
        self.file_path_entry = ttk.Entry(self.breakdown_jobs_window, width=60, textvariable=self.file_path_var)
        self.file_path_entry.grid(column=1, row=0, padx=5, pady=5, sticky="ew")
        self.browse_button = ttk.Button(self.breakdown_jobs_window, text="Browse", command=self.browse_file)
        self.browse_button.grid(column=2, row=0, padx=5, pady=5, sticky="ew")

        self.load_button = ttk.Button(self.breakdown_jobs_window, text="Load from Excel", command=self.load_from_excel)
        self.load_button.grid(column=3, row=0, padx=5, pady=5, sticky="ew")

        # Create the Treeview widget
        self.tree = ttk.Treeview(self.breakdown_jobs_window, columns=("Job Category", "Percentage"), show='headings')
        self.tree.heading("Job Category", text="Job Category")
        self.tree.heading("Percentage", text="Percentage")
        self.tree.column("Job Category", width=400)
        self.tree.column("Percentage", width=100)
        self.tree.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="nsew")

        # Add default job categories and percentages


        # Scrollbar for the Treeview
        self.scrollbar = ttk.Scrollbar(self.breakdown_jobs_window, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.grid(row=1, column=4, sticky="ns")

        # Frame for the buttons to control layout
        button_frame = ttk.Frame(self.breakdown_jobs_window)
        button_frame.grid(column=0, row=2, columnspan=4, pady=5, sticky="ew")

        button_width = 12  # Set a consistent width for buttons
        self.add_button = ttk.Button(button_frame, text="Add Row", command=self.add_row, width=button_width)
        self.add_button.grid(column=0, row=0, padx=(0, 5))
        self.edit_button = ttk.Button(button_frame, text="Edit Row", command=self.edit_row, width=button_width)
        self.edit_button.grid(column=1, row=0, padx=(0, 5))
        self.delete_button = ttk.Button(button_frame, text="Delete Row", command=self.delete_row, width=button_width)
        self.delete_button.grid(column=2, row=0, padx=(0, 5))

        self.save_button = ttk.Button(button_frame, text="Save and Calculate", command=self.save_job_breakdown, width=button_width * 2)
        # Last button setup
        self.save_button.grid(column=3, row=0, padx=(0, 5))

        # --- Make the window modal and focused ---
        self.breakdown_jobs_window.transient(self.parent)
        self.breakdown_jobs_window.grab_set()
        self.breakdown_jobs_window.focus_set()
        self.breakdown_jobs_window.wait_window()



    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            self.file_path_var.set(file_path)

    def load_from_excel(self):
        file_path = self.file_path_var.get()
        if not file_path:
            messagebox.showerror("Error", "Please select an Excel file first.")
            return

        try:
            df = pd.read_excel(file_path)
            if 'Occupation title' in df.columns and 'Percent of total employment' in df.columns:
                categories = df['Occupation title'].tolist()
                percentages = df['Percent of total employment'].tolist()

                # Clear existing entries
                for item in self.tree.get_children():
                    self.tree.delete(item)

                for category, percentage in zip(categories, percentages):
                    self.tree.insert("", "end", values=(category, f"{round(percentage)}"))

                messagebox.showinfo("Success", "File loaded and entries added successfully.")
            else:
                messagebox.showerror("Error",
                                     "The Excel file must contain 'Occupation title' and 'Percent of total employment' columns.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read Excel file: {e}")

    def save_job_breakdown(self):
        job_breakdown = {}

        for row in self.tree.get_children():
            category, percent = self.tree.item(row)['values']
            try:
                percent = round(float(percent))  # Convert percentage to integer
                job_breakdown[category] = percent
            except ValueError:
                messagebox.showerror("Error",
                                     f"Invalid percentage value for category '{category}'. Please ensure all percentages are numbers.")
                return

        total_percentage = sum(job_breakdown.values())
        if not (99 <= total_percentage <= 101):
            messagebox.showerror("Error", "Total percentage must be close to 100% (within ±1%).")
            return

        self.job_breakdown_callback(job_breakdown)
        self.breakdown_jobs_window.destroy()
        messagebox.showinfo("Success", "Job breakdown saved successfully.")

    def add_row(self):
        self.tree.insert("", "end", values=("New Category", f"{0:.2f}"))

    def delete_row(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a row to delete.")
            return
        for item in selected_item:
            self.tree.delete(item)

    def edit_row(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror("Error", "Please select a row to edit.")
            return

        item = selected_item[0]
        category, percent = self.tree.item(item, "values")

        edit_window = tk.Toplevel(self.breakdown_jobs_window)
        edit_window.title("Edit Row")
        edit_window.geometry("300x150")

        tk.Label(edit_window, text="Job Category:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        category_var = StringVar(value=category)
        category_entry = ttk.Entry(edit_window, textvariable=category_var)
        category_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        tk.Label(edit_window, text="Percentage:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        percent_var = StringVar(value=percent)
        percent_entry = ttk.Entry(edit_window, textvariable=percent_var)
        percent_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        def save_changes():
            new_category = category_var.get()
            new_percent = percent_var.get()
            try:
                new_percent = round(float(new_percent))
                if new_percent < 0 or new_percent > 100:
                    raise ValueError
                self.tree.item(item, values=(new_category, f"{new_percent}"))
                edit_window.destroy()
            except ValueError:
                messagebox.showerror("Error", "Percentage must be a number between 0 and 100.")

        save_button = ttk.Button(edit_window, text="Save", command=save_changes)
        save_button.grid(row=2, column=0, columnspan=2, pady=10)

        edit_window.transient(self.breakdown_jobs_window)
        edit_window.grab_set()
        edit_window.focus_set()

        edit_window.mainloop()

# Example usage
if __name__ == "__main__":
    def job_breakdown_callback(job_breakdown):
        print("Job Breakdown:", job_breakdown)

    root = tk.Tk()
    root.withdraw()
    BreakdownJobsPopup(root, job_breakdown_callback)
    root.mainloop()
