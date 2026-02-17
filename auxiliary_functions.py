from PIL import Image
from werkzeug.utils import secure_filename
import uuid
import os

def Save_and_resize_image(file, upload_folder, size=(800, 800)):
    filename = secure_filename(file.filename)

    # nombre único
    ext = filename.rsplit(".", 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_folder, unique_name)

    image = Image.open(file)
    image = image.convert("RGB")  # evita errores con PNG/WEBP
    image.thumbnail(size, Image.LANCZOS)

    # fondo blanco si no es cuadrada
    background = Image.new("RGB", size, (255, 255, 255))
    offset = (
        (size[0] - image.size[0]) // 2,
        (size[1] - image.size[1]) // 2
    )
    background.paste(image, offset)

    background.save(filepath, format="JPEG", quality=85)

    return unique_name


