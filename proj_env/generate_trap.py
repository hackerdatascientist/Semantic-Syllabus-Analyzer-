import xlsxwriter

def create_honey_excel(token_id, file_name):
    # 1. Define your Phase 1 server URL (Replace with your actual IP/Domain)
    tracking_url = f"https://unproductive-dictatorially-tien.ngrok-free.dev/track/token_123"
    
    # 2. Create the Excel file
    workbook = xlsxwriter.Workbook(file_name)
    worksheet = workbook.add_worksheet()

    # 3. Add "Bait" content to make it look real
    worksheet.write('A1', 'Username')
    worksheet.write('B1', 'Password (Encrypted)')
    worksheet.write('A2', 'admin_root')
    worksheet.write('B2', '5e884898da28047151d0e56f8dc6292773603d0d') # Fake SHA-256 hash
    worksheet.write('A3', 'db_backup_user')
    worksheet.write('B3', '76a2173be6393254e72ffa4d6df1030a1b5d173b')

    # 4. THE TRAP: Insert a "Remote Image"
    # We make the image 1x1 pixel and hide it in a far-off cell (like Z100)
    # When the file opens, Excel hits the URL to 'download' the image.
    worksheet.insert_image('H1', r"C:\Users\ASUS\Documents\Mini_Project_sem_6\Semantic_Syllabus_analysist\proj_env\1.png", {'url': tracking_url})

    workbook.close()
    print(f"Successfully created honey token: {file_name}")

# Run the generator
create_honey_excel("token_123", "Company_Server_Passwords_2026.xlsx")