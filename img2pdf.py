import os
from PIL import Image

def images_to_pdf(folder_path, output_pdf):
    files = os.listdir(folder_path)

    image_files = [f for f in files if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]

    image_files.sort()

    if not image_files:
        print("Aucune image trouvée dans le dossier.")
        return

    image_list = []

    for i, filename in enumerate(image_files):
        img_path = os.path.join(folder_path, filename)
        img = Image.open(img_path).convert("RGB")
        image_list.append(img)

    first_image = image_list[0]
    rest = image_list[1:]

    first_image.save(output_pdf, save_all=True, append_images=rest)

    print(f"PDF créé : {output_pdf}")


# Exemple d'utilisation :
images_to_pdf(
    folder_path=r"C:\Users\Vous\Images",           # Dossier avec les images
    output_pdf=r"C:\Users\Vous\output.pdf"         # PDF final
)
