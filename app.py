import os
import math
from flask import Flask, request, send_file, render_template_string
import pyembroidery

app = Flask(__name__)

# The core density calculation logic
def process_density(input_bytes, scale_factor=0.80):
    # Read the data from binary memory
    pattern = pyembroidery.read_bytes(input_bytes)
    if not pattern:
        return None

    original_stitches = pattern.stitches
    optimized_pattern = pyembroidery.EmbPattern()
    optimized_pattern.threadlist = pattern.threadlist

    last_x, last_y = 0, 0
    min_safe_distance = 4.0  # 0.4mm distance rule to protect threads

    for idx, stitch in enumerate(original_stitches):
        x, y, flags = stitch
        target_x = round(x * scale_factor)
        target_y = round(y * scale_factor)
        
        # Keep jump flags and edges untouched
        if flags != 0 or idx == 0 or idx == len(original_stitches) - 1:
            optimized_pattern.add_stitch_absolute(flags, target_x, target_y)
            last_x, last_y = target_x, target_y
        else:
            distance = math.sqrt((target_x - last_x)**2 + (target_y - last_y)**2)
            if distance >= min_safe_distance:
                optimized_pattern.add_stitch_absolute(flags, target_x, target_y)
                last_x, last_y = target_x, target_y

    # Write the output pattern to bytes in memory
    return pyembroidery.write_bytes(optimized_pattern, "out.pes")

# Route to display the webpage
@app.route('/')
def home():
    with open('index.html', 'r') as f:
        return render_template_string(f.read())

# Route that handles the file conversion request
@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    scale = float(request.form.get('scale', 0.80))
    
    if file.filename == '':
        return "No selected file", 400

    file_bytes = file.read()
    output_bytes = process_density(file_bytes, scale)
    
    if not output_bytes:
        return "Failed to process embroidery file structural alignment.", 500

    # Save to a temporary array and stream back to phone
    temp_path = "temp_output.pes"
    with open(temp_path, "wb") as f:
        f.write(output_bytes)

    return send_file(temp_path, as_attachment=True, download_name=f"fixed_{int(scale*100)}pct_{file.filename}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
