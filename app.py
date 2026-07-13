import os
import math
import io
from flask import Flask, request, send_file, render_template_string
import pyembroidery

app = Flask(__name__)

def process_density(input_bytes, scale_factor=0.80):
    # Create an in-memory stream from the uploaded file bytes
    input_stream = io.BytesIO(input_bytes)
    
    # Read the pattern using the stream-reader interface
    pattern = pyembroidery.read_pes(input_stream)
    if not pattern:
        return None

    original_stitches = pattern.stitches
    optimized_pattern = pyembroidery.EmbPattern()
    optimized_pattern.threadlist = pattern.threadlist

    last_x, last_y = 0, 0
    min_safe_distance = 4.0  # 0.4mm protective threshold

    for idx, stitch in enumerate(original_stitches):
        x, y, flags = stitch
        target_x = round(x * scale_factor)
        target_y = round(y * scale_factor)
        
        if flags != 0 or idx == 0 or idx == len(original_stitches) - 1:
            optimized_pattern.add_stitch_absolute(flags, target_x, target_y)
            last_x, last_y = target_x, target_y
        else:
            distance = math.sqrt((target_x - last_x)**2 + (target_y - last_y)**2)
            if distance >= min_safe_distance:
                optimized_pattern.add_stitch_absolute(flags, target_x, target_y)
                last_x, last_y = target_x, target_y

    # Write output to an in-memory stream instead of a physical file
    output_stream = io.BytesIO()
    pyembroidery.write_pes(optimized_pattern, output_stream)
    output_stream.seek(0) # Reset stream pointer to beginning
    return output_stream

@app.route('/')
def home():
    try:
        with open('index.html', 'r') as f:
            return render_template_string(f.read())
    except FileNotFoundError:
        return "Error: index.html file missing from repository", 500

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return "No file part", 400
    file = request.files['file']
    scale = float(request.form.get('scale', 0.80))
    
    if file.filename == '':
        return "No selected file", 400

    try:
        file_bytes = file.read()
        output_io = process_density(file_bytes, scale)
        
        if not output_io:
            return "Failed to process embroidery file structural alignment.", 500

        # Stream directly back to the phone out of memory
        return send_file(
            output_io,
            as_attachment=True,
            download_name=f"fixed_{int(scale*100)}pct_{file.filename}",
            mimetype="application/octet-stream"
        )
    except Exception as e:
        return f"Application crashed: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
