import os
import io
import math
from flask import Flask, request, send_file, render_template_string
import pyembroidery

app = Flask(__name__)

def advanced_density_engine(input_bytes, percent_change, scale_size_together):
    input_stream = io.BytesIO(input_bytes)
    pattern = pyembroidery.read_pes(input_stream)
    if not pattern or not pattern.stitches:
        return None

    original_stitches = pattern.stitches
    optimized_pattern = pyembroidery.EmbPattern()
    optimized_pattern.threadlist = pattern.threadlist

    # Calculate multiplier factors based on user input
    factor = 1.0 + (percent_change / 100.0)
    if factor <= 0.1:
        factor = 0.1  # Safety guard limit

    # Step 1: If size scaling is toggled ON, apply spatial resizing first
    geom_scale = factor if scale_size_together else 1.0

    # Step 2: Calculate density shift adjustments
    # FIXED SYNTAX HERE: Using 'not' instead of '!' for Python standards
    spacing_compensation = 1.0 / math.sqrt(factor) if (not scale_size_together and percent_change < 0) else 1.0

    last_x, last_y = 0, 0
    accumulator = 0.0

    # Locate centroid bounding coordinate to safely scale from the true center point
    xs = [s[0] for s in original_stitches]
    ys = [s[1] for s in original_stitches]
    cx = (max(xs) + min(xs)) / 2 if xs else 0
    cy = (max(ys) + min(ys)) / 2 if ys else 0

    if percent_change < 0:
        # THINNING WITH SPATIAL RE-BALANCING
        for idx, stitch in enumerate(original_stitches):
            x, y, flags = stitch
            
            # Map standard coordinates relative to center alignment frame
            tx = round(cx + (x - cx) * geom_scale * spacing_compensation)
            ty = round(cy + (y - cy) * geom_scale * spacing_compensation)
            
            if flags != 0 or idx == 0 or idx == len(original_stitches) - 1:
                optimized_pattern.add_stitch_absolute(flags, tx, ty)
                last_x, last_y = tx, ty
            else:
                accumulator += factor
                if accumulator >= 1.0:
                    # Validate distance before placing to prevent extreme cluster nodes
                    dist = math.sqrt((tx - last_x)**2 + (ty - last_y)**2)
                    if dist > 1.5: 
                        optimized_pattern.add_stitch_absolute(flags, tx, ty)
                        last_x, last_y = tx, ty
                    accumulator -= 1.0
    else:
        # FILL DENSITY INJECTION WITH BOUNDS HOLD
        for idx, stitch in enumerate(original_stitches):
            x, y, flags = stitch
            tx = round(cx + (x - cx) * geom_scale)
            ty = round(cy + (y - cy) * geom_scale)
            
            optimized_pattern.add_stitch_absolute(flags, tx, ty)
            
            if flags == 0 and idx < len(original_stitches) - 1:
                next_x, next_y, next_flags = original_stitches[idx + 1]
                if next_flags == 0:
                    accumulator += (factor - 1.0)
                    while accumulator >= 1.0:
                        ntx = round(cx + (next_x - cx) * geom_scale)
                        nty = round(cy + (next_y - cy) * geom_scale)
                        
                        # Generate interpolated smooth step stitch coordinates
                        mid_x = round((tx + ntx) / 2)
                        mid_y = round((ty + nty) / 2)
                        optimized_pattern.add_stitch_absolute(0, mid_x, mid_y)
                        accumulator -= 1.0
            last_x, last_y = tx, ty

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
        return "Error: index.html missing", 500

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return "No file uploaded", 400
    file = request.files['file']
    
    try:
        density_val = float(request.form.get('density', 0))
    except ValueError:
        density_val = 0.0
        
    scale_size = request.form.get('scale_size') == 'on'

    if file.filename == '':
        return "No file selected", 400

    try:
        output_io = advanced_density_engine(file.read(), density_val, scale_size)
        if not output_io:
            return "Failed to convert file geometry layers.", 500

        mode = "sync_scale" if scale_size else "fixed_dimensions"
        return send_file(
            output_io,
            as_attachment=True,
            download_name=f"{mode}_{int(density_val)}pct_{file.filename}",
            mimetype="application/octet-stream"
        )
    except Exception as e:
        return f"Processing Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
