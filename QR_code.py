import qrcode
import numpy as np
import trimesh
from PIL import Image

def generate_qr_image(url, filename="qr.png"):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    print(f"[+] Saved QR code image to {filename}")
    return img

def image_to_matrix(image):
    # Convert image to binary matrix: 1 for black, 0 for white
    image = image.convert('L')
    data = np.asarray(image)
    return (data < 128).astype(np.uint8)  # black = 1, white = 0

def matrix_to_stl(matrix, cube_size=1.0, height=2.0, plate_thickness=1.0, output_file='qr_code.stl'):
    shapes = []
    rows, cols = matrix.shape

    # Add background plate
    plate_width = cols * cube_size
    plate_height = rows * cube_size
    background = trimesh.creation.box(extents=[plate_width, plate_height, plate_thickness])
    background.apply_translation([
        plate_width / 2.0,
        -plate_height / 2.0,
        plate_thickness / 2.0
    ])
    shapes.append(background)

    # Add QR code cubes
    for y in range(rows):
        for x in range(cols):
            if matrix[y, x] == 1:  # black square
                cube = trimesh.creation.box(extents=[cube_size, cube_size, height])
                cube.apply_translation([
                    x * cube_size + cube_size / 2.0,
                    -y * cube_size - cube_size / 2.0,
                    plate_thickness + height / 2.0
                ])
                shapes.append(cube)

    combined = trimesh.util.concatenate(shapes)
    combined.export(output_file)
    print(f"[+] STL file with background saved as {output_file}")

def main():
    url = input("Enter the URL to encode in QR code: ").strip()
    qr_image = generate_qr_image(url, "qr_code.png")
    matrix = image_to_matrix(qr_image)
    matrix_to_stl(matrix, cube_size=1.0, height=2.0, output_file="qr_code.stl")

if __name__ == "__main__":
    main()