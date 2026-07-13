import pyembroidery
import math

def adjust_pes_density(input_file_path, output_file_path, scale_factor=0.80):
    # 1. Read the .pes file using a production-grade parser
    pattern = pyembroidery.read(input_file_path)
    
    if not pattern:
        print("Error: Could not read or decode the embroidery file.")
        return False

    # 2. Extract all structural stitches from the object container
    original_stitches = pattern.stitches
    optimized_pattern = pyembroidery.EmbPattern()
    
    # Keep the original color palette/thread information completely intact
    optimized_pattern.threadlist = pattern.threadlist

    last_x, last_y = 0, 0
    min_safe_distance = 4.0  # 0.4mm threshold in embroidery coordinate units

    # 3. Process each needle point through a spatial grid filter
    for idx, stitch in enumerate(original_stitches):
        x, y, flags = stitch
        
        # Scale the geometric coordinates down
        target_x = round(x * scale_factor)
        target_y = round(y * scale_factor)
        
        # Always keep command flags like JUMP, COLOR_BREAK, END, or the first/last stitch
        # pyembroidery flags: 0 = STITCH, 1 = JUMP, 2 = TRIM, 4 = COLOR_BREAK, 8 = END
        if flags != 0 or idx == 0 or idx == len(original_stitches) - 1:
            optimized_pattern.add_stitch_absolute(flags, target_x, target_y)
            last_x, last_y = target_x, target_y
        else:
            # Calculate actual physical distance between needle penetrations
            distance = math.sqrt((target_x - last_x)**2 + (target_y - last_y)**2)
            
            # Density Check: Only add the stitch if it won't bunch up thread
            if distance >= min_safe_distance:
                optimized_pattern.add_stitch_absolute(flags, target_x, target_y)
                last_x, last_y = target_x, target_y

    # 4. Write back to a perfectly formatted, uncorrupted .pes file
    # The library handles building the binary headers, tables, and PEC blocks automatically
    pyembroidery.write(optimized_pattern, output_file_path)
    
    print(f"Success! Scaled to {int(scale_factor*100)}%.")
    print(f"Original Stitches: {len(original_stitches)}")
    print(f"Optimized Stitches: {len(optimized_pattern.stitches)}")
    return True

# Example Usage:
# adjust_pes_density("flower_large.pes", "flower_optimized.pes", scale_factor=0.80)
