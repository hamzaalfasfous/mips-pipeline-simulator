import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import re
import csv

STAGES_MODE_1 = ['IF', 'RR', 'EX', 'MA', 'WR']
STAGES_MODE_2 = ['IF', 'RR', 'EX', 'MA', 'WR']
STALL_COUNT = 3

ARITH_OPS = {'add', 'sub', 'div', 'mult'}
LOAD_OPS = {'lw'}
STORE_OPS = {'sw'}

SAMPLE_INSTRUCTIONS = """
I1- lw $t1, 0($t0)
I2- lw $t2, 4($t0)
I3- add $t3, $t1, $t2
I4- sw $t3, 12($t0)
I5- lw $t4, 8($t0)
I6- add $t5, $t1, $t4
I7- sw $t5, 16($t0)
"""


class PipelineSimulator:
    def __init__(self, root):
        """
        Initializes the GUI for the MIPS pipeline simulator.
        Sets up input area, buttons, canvas, and output table.
        """
        self.root = root
        self.root.title("MIPS Pipeline Simulator")

        self.last_schedule = []
        self.last_instruction_ids = []

        # tk.Label(root, text="Select Simulation Mode:").pack()
        # self.mode_var = tk.StringVar(value="Strict Reordering")
        # self.mode_menu = ttk.Combobox(root, textvariable=self.mode_var,
        #                               values=["Strict Reordering", "No Prevention Techniques"], state="readonly")
        # self.mode_menu.pack()

        tk.Label(root, text="Edit Instructions:").pack()
        self.text = tk.Text(root, height=14, width=70, wrap="none")
        self.text.insert("1.0", SAMPLE_INSTRUCTIONS.strip())
        self.text.pack(expand=True, fill="both")

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Simulate", command=self.simulate).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Load from File", command=self.load_from_file).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="Export to CSV", command=self.export_to_csv).pack(side=tk.LEFT, padx=10)

        self.log_text = tk.Text(root, height=6, width=70, wrap="word", bg="#f0f0f0")
        self.log_text.pack()

        self.canvas = tk.Canvas(root)
        self.canvas.pack(side=tk.TOP, fill="both", expand=True)

        self.h_scroll = tk.Scrollbar(root, orient="horizontal", command=self.canvas.xview)
        self.h_scroll.pack(side=tk.BOTTOM, fill="x")

        self.canvas.configure(xscrollcommand=self.h_scroll.set)
        self.canvas.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        self.table_frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.table_frame, anchor="nw")

    def load_from_file(self):
        """
        Opens a file dialog to load instructions from a text file
        and insert them into the instruction text box.
        """
        filepath = filedialog.askopenfilename(
            title="Select Instruction File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath:
            return

        try:
            with open(filepath, 'r') as file:
                content = file.read()
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{e}")

    def parse_instruction(self, line):
        """
        Parses a single instruction line into a dictionary.

        Returns:
            dict or None: Parsed instruction or None if not valid.
        """
        match_r = re.match(r'I(\d+)-\s*(\w+)\s*\$(\w+),\s*\$(\w+),\s*\$(\w+)', line)
        match_lw = re.match(r'I(\d+)-\s*lw\s*\$(\w+),\s*(\d+)?\(\$(\w+)\)', line)
        match_sw = re.match(r'I(\d+)-\s*sw\s*\$(\w+),\s*(\d+)?\(\$(\w+)\)', line)
        match_alt = re.match(r'I(\d+)-\s*(\w+)\s*\$(\w+),\s*\$(\w+),\s*(\d+|\$\w+)', line)

        if match_r:
            idx, op, dest, src1, src2 = match_r.groups()
            return {'id': f"I{idx}", 'op': op.lower(), 'type': 'r'}
        elif match_lw:
            idx, dest, offset, base = match_lw.groups()
            return {'id': f"I{idx}", 'op': 'lw', 'type': 'lw'}
        elif match_sw:
            idx, src, offset, base = match_sw.groups()
            return {'id': f"I{idx}", 'op': 'sw', 'type': 'sw'}
        elif match_alt:
            idx, op, dest, src1, src2 = match_alt.groups()
            return {'id': f"I{idx}", 'op': op.lower(), 'dest': f"${dest}", 'src1': f"${src1}", 'src2': src2, 'type': 'parsed'}
        return None

    def reorder_instructions(self, instructions):
        """
        Moves all 'lw' instructions to the top of the instruction list.
        Used in Strict Reordering mode.
        """
        loads = [instr for instr in instructions if instr.get('op') in LOAD_OPS]
        others = [instr for instr in instructions if instr.get('op') not in LOAD_OPS]
        self.log_text.insert(tk.END, "Reordering Loads to the Top...\n")
        return loads + others

    def get_stall_count(self, instr):
        """
        Returns the number of stall cycles required based on instruction type.
        """
        if instr['type'] == 'r' and instr['op'] in ARITH_OPS:
            return STALL_COUNT
        elif instr['op'] == 'sw':
            return STALL_COUNT
        return 0

    def simulate(self):
        """
        Main handler: reads input, determines mode, and runs simulation.
        """
        for widget in self.table_frame.winfo_children():
            widget.destroy()
        self.log_text.delete("1.0", tk.END)

        # mode = self.mode_var.get()
        mode = "No Prevention Techniques"

        text_content = self.text.get("1.0", tk.END).strip()
        if not text_content:
            messagebox.showerror("Error", "Please enter some instructions.")
            return

        lines = text_content.splitlines()
        instructions = [self.parse_instruction(line) for line in lines if self.parse_instruction(line)]

        if not instructions:
            messagebox.showerror("Error", "No valid instructions found!")
            return

        if mode == "Strict Reordering":
            instructions = self.reorder_instructions(instructions)
            schedule = self.simulate_mode1(instructions)
        else:
            schedule = self.simulate_mode2(instructions)

        self.last_schedule = schedule
        self.last_instruction_ids = [i['id'] for i in instructions]
        self.display_schedule(schedule, self.last_instruction_ids)

    def simulate_mode1(self, instructions):
        """
        Simulates pipeline with 'Strict Reordering' logic.
        """
        schedule = []
        cycle_positions = []

        for i, instr in enumerate(instructions):
            start_cycle = cycle_positions[i-1] if i > 0 else 0
            row = [''] * start_cycle + ['IF']

            if instr['op'] in ARITH_OPS:
                row += ['stall', 'stall']
            elif instr['op'] in STORE_OPS:
                row += ['stall', 'stall', 'stall']

            row += STAGES_MODE_1[1:]
            rr_cycle = row.index('RR')
            cycle_positions.append(rr_cycle)
            schedule.append(row)

        return schedule

    def simulate_mode2(self, instructions):
        """
        Simulates pipeline with 'No Prevention Techniques' logic.
        """
        schedule = []
        current_cycle = 0

        for i, instr in enumerate(instructions):
            stalls = self.get_stall_count(instr)
            if i == 0:
                stalls = 0

            while True:
                conflict = False
                for row in schedule:
                    if current_cycle < len(row) and row[current_cycle] == '-':
                        current_cycle += 1
                        conflict = True
                        break
                if not conflict:
                    break

            row = [''] * current_cycle + ['IF']
            if stalls > 0:
                row += ['-'] * stalls

            row += STAGES_MODE_2[1:]
            schedule.append(row)
            current_cycle += 1

        return schedule

    def display_schedule(self, schedule, instruction_names):
        """
        Draws the schedule table on the GUI.
        """
        max_cycles = max(len(row) for row in schedule)
        ttk.Label(self.table_frame, text="Instruction").grid(row=0, column=0, padx=5, pady=5)
        for c in range(max_cycles):
            ttk.Label(self.table_frame, text=f"C{c+1}").grid(row=0, column=c+1, padx=5, pady=5)

        for r, row in enumerate(schedule):
            ttk.Label(self.table_frame, text=instruction_names[r]).grid(row=r+1, column=0, padx=5, pady=5)
            for c in range(max_cycles):
                val = row[c] if c < len(row) else ""
                display = "-" if val in ["stall", "-"] else val
                label = tk.Label(self.table_frame, text=display, borderwidth=1, relief="solid", width=10)
                if val in ["stall", "-"]:
                    label.config(bg="orange")
                elif val == 'IF':
                    label.config(bg="lightblue")
                elif val != '':
                    label.config(bg="lightgreen")
                label.grid(row=r+1, column=c+1, padx=1, pady=1)

    def export_to_csv(self):
        """
        Exports the simulation result to a CSV file using file dialog.
        """
        if not self.last_schedule:
            messagebox.showerror("Error", "No simulation results to export.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            title="Save Schedule as CSV"
        )

        if not filepath:
            return

        try:
            max_cycles = max(len(row) for row in self.last_schedule)

            with open(filepath, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["Instruction"] + [f"C{c+1}" for c in range(max_cycles)])
                for instr_id, row in zip(self.last_instruction_ids, self.last_schedule):
                    full_row = row + [''] * (max_cycles - len(row))
                    writer.writerow([instr_id] + full_row)

            messagebox.showinfo("Success", f"Schedule exported successfully to:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export CSV:\n{e}")


if __name__ == '__main__':
    try:
        root = tk.Tk()
        app = PipelineSimulator(root)
        root.mainloop()
    except Exception as e:
        print("GUI failed to initialize. Ensure tkinter is installed and GUI is supported.")
        print(e)