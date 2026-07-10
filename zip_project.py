import zipfile
import os

def create_zip():
    folders_to_zip = ['etsypulse', 'keywords', 'rank_optimizer', 'profit_pulse', 'mockups', 'keyword_bank', 'etsy_researcher', 'customer_detail', 'pinterest_seo', 'competitor_shop_analysis']
    files_to_zip = ['manage.py', 'requirements.txt']
    
    with zipfile.ZipFile('atifzak_update.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
        for folder in folders_to_zip:
            for root, dirs, files in os.walk(folder):
                if '__pycache__' in dirs:
                    dirs.remove('__pycache__')
                for file in files:
                    if file.endswith('.pyc'):
                        continue
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, arcname=file_path)
                    
        for file in files_to_zip:
            if os.path.exists(file):
                zipf.write(file, arcname=file)

if __name__ == "__main__":
    create_zip()
    print("Zip file created successfully as atifzak_update.zip")
