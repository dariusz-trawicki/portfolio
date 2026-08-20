
import os
from fpdf import FPDF

# Ensure directory exists
os.makedirs("pdfs", exist_ok=True)

def txt_to_pdf(txt_path, output_path="pdfs/sample.pdf"):
    with open(txt_path, "r", encoding="utf-8") as f:
        content = f.readlines()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for line in content:
        pdf.cell(200, 10, txt=line.strip(), ln=True)

    pdf.output(output_path)
    print(f"✅ PDF saved to {output_path}")

# Example usage
if __name__ == "__main__":
    txt_file_path = "sample.txt" 
    txt_to_pdf(txt_file_path)
