import os
import io
from flask import Flask, request, send_file, render_template_string
import pyembroidery

app = Flask(__name__)

def adjust_stitch_density(input_bytes, density_pct):
    input_stream = io.BytesIO(input_bytes)
    pattern = pyembroidery.read_pes(input_stream)
    if not pattern:
        return None

    original_stitches = pattern.stitches
    optimized_pattern = pyembroidery.EmbPattern()
    optimized_pattern.threadlist = pattern.threadlist

    if not original_stitches:
        return None

    # Calculate removal or addition factor
    # If density_pct is negative (e.g., -20), we want to keep roughly 80% of normal stitches.
    # If positive (e.g., 20), we want to inject extra intermediate stitches.
    
    if density_pct < 0:
        # REMOVE STITCHES (Thinning out density)
        keep_ratio = (100 + density_pct) / 100.0  # e.g., -20% -> keep 0.80
        if keep_ratio <= 0:
            keep_ratio = 0.1  # Safety fallback boundary
            
        accumulator = 0.0
        for idx, stitch in enumerate(original_stitches):
            x, y, flags = stitch
            
            # Lock the critical anchor commands (Jumps, Ends, Color trims, First/Last points)
            if flags != 0 or idx == 0 or idx == len(original_stitches) - 1:
                optimized_pattern.add_stitch_absolute(flags, x, y)
            else:
                accumulator += keep_ratio
                if accumulator >= 1.0:
                    optimized_pattern.add_stitch_absolute(flags, x, y)
                    accumulator -= 1.0
    else:
        # ADD STITCHES (Increasing density via midpoint interpolation)
        add_ratio = density_pct / 100.0  # e.g., 20% -> 0.20 extra stitches
        accumulator = 0.0
        
        for idx, stitch in enumerate(original_stitches):
            x, y, flags = stitch
            optimized_pattern.add_stitch_absolute(flags, x, y)
            
            # Don't interpolate after structural command flags or on the last element
            if flags == 0 and idx < len(original_stitches) - 1:
                next_x, next_y, next_flags = original_stitches[idx + 1]
                if next_flags == 0:
                    accumulator += add_ratio
                    if accumulator >= 1.0:
                        # Insert a clean intermediate balancing midpoint stitch coordinate
                        mid_x = round((x + next_x) / 2)
                        mid_y = round((y + next_y) / 2)
                        optimized_pattern.add_stitch_absolute(0, mid_x, mid_y)
                        accumulator -= 1.0

    output_stream = io.BytesIO()
    pyembroidery.write_pes(optimized_pattern, output_stream)
    output_stream.seek(0)
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
    
    try:
        density_val = float(request.form.get('density', 0))
    except ValueError:
        density_val = 0.0
        
    if file.filename == '':
        return "No selected file", 400

    try:
        file_bytes = file.read()
        output_io = adjust_stitch_density(file_bytes, density_val)
        
        if not output_io:
            return "Failed to process embroidery file density geometry mapping.", 500

        label = f"plus_{int(density_val)}" if density_val >= 0 else f"minus_{int(abs(density_val))}"
        return send_file(
            output_io,
            as_attachment=True,
            download_name=f"fixed_size_{label}pct_{file.filename}",
            mimetype="application/octet-stream"
        )
    except Exception as e:
        return f"Application crashed: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
