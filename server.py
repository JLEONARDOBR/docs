import os
import uuid
import zipfile
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from urllib.parse import parse_qs

# NVAI endpoint for the ocdrnet NIM
nvai_url = "https://ai.api.nvidia.com/v1/cv/nvidia/ocdrnet"
header_auth = "Bearer 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"

def _upload_asset(input_file, description):
    """
    Uploads an asset to the NVCF API.
    :param input_file: The file object to upload
    :param description: A description of the asset
    :return: UUID of the uploaded asset
    """
    assets_url = "https://api.nvcf.nvidia.com/v2/nvcf/assets"

    headers = {
        "Authorization": header_auth,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    s3_headers = {
        "x-amz-meta-nvcf-asset-description": description,
        "content-type": "image/jpeg",
    }

    payload = {"contentType": "image/jpeg", "description": description}

    response = requests.post(assets_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()

    asset_url = response.json()["uploadUrl"]
    asset_id = response.json()["assetId"]

    response = requests.put(
        asset_url,
        data=input_file,
        headers=s3_headers,
        timeout=300,
    )
    response.raise_for_status()
    return uuid.UUID(asset_id)

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes('''
                <!doctype html>
                <html>
                <head>
                    <style>
                        body {
                            background: linear-gradient(to right, #00aaff, #00ffcc);
                            font-family: Arial, sans-serif;
                            text-align: center;
                            color: #333;
                        }
                        h1 {
                            font-size: 2.5em;
                            margin-top: 20px;
                        }
                        .container {
                            width: 80%;
                            margin: auto;
                            padding: 20px;
                            background: white;
                            border-radius: 8px;
                            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                        }
                        input[type="file"] {
                            margin: 20px 0;
                        }
                        input[type="submit"] {
                            background-color: #007bff;
                            color: white;
                            border: none;
                            padding: 10px 20px;
                            border-radius: 5px;
                            font-size: 1.1em;
                            cursor: pointer;
                        }
                        input[type="submit"]:hover {
                            background-color: #0056b3;
                        }
                        .response-content {
                            text-align: left;
                            margin-top: 20px;
                        }
                        .response-content pre {
                            background: #f1f1f1;
                            border: 1px solid #ddd;
                            padding: 10px;
                            border-radius: 5px;
                            overflow-x: auto;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>FastProBR - Extraindo Dados de Documentos para Cadastros</h1>
                        <form action="/upload" method="post" enctype="multipart/form-data">
                            <input type="file" name="file" accept="image/jpeg">
                            <input type="submit" value="Upload">
                        </form>
                    </div>
                </body>
                </html>
            ''', 'utf-8'))
        elif self.path.startswith('/result'):
            # Show results page
            query_params = parse_qs(self.path.split('?')[1])
            response_content = query_params.get('response', [''])[0]
            files = query_params.get('files', [''])
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(bytes(f'''
                <!doctype html>
                <html>
                <head>
                    <style>
                        body {{
                            background: linear-gradient(to right, #00aaff, #00ffcc);
                            font-family: Arial, sans-serif;
                            text-align: center;
                            color: #333;
                        }}
                        h1 {{
                            font-size: 2.5em;
                            margin-top: 20px;
                        }}
                        .container {{
                            width: 80%;
                            margin: auto;
                            padding: 20px;
                            background: white;
                            border-radius: 8px;
                            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
                        }}
                        .response-content {{
                            text-align: left;
                            margin-top: 20px;
                        }}
                        .response-content pre {{
                            background: #f1f1f1;
                            border: 1px solid #ddd;
                            padding: 10px;
                            border-radius: 5px;
                            overflow-x: auto;
                        }}
                        .files-list {{
                            margin-top: 20px;
                            text-align: left;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>FastProBR - Resultados</h1>
                        <div class="response-content">
                            <h2>Dados do Arquivo .response:</h2>
                            <pre>{response_content}</pre>
                        </div>
                        <div class="files-list">
                            <h2>Arquivos Processados:</h2>
                            <ul>
                                {''.join(f'<li>{file}</li>' for file in files)}
                            </ul>
                        </div>
                    </div>
                </body>
                </html>
            ''', 'utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/upload':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            boundary = self.headers['Content-Type'].split("boundary=")[1].encode()
            parts = post_data.split(boundary)
            file_data = None

            for part in parts:
                if b'Content-Disposition: form-data; name="file"' in part:
                    file_start = part.find(b'\r\n\r\n') + 4
                    file_end = part.find(b'\r\n--', file_start)
                    file_data = part[file_start:file_end]
            
            if file_data:
                image_path = os.path.join('uploads', 'uploaded_image.jpg')
                os.makedirs(os.path.dirname(image_path), exist_ok=True)
                
                with open(image_path, 'wb') as f:
                    f.write(file_data)

                # Upload to NVCF and process
                try:
                    asset_id = _upload_asset(BytesIO(file_data), "Input Image")

                    inputs = {"image": f"{asset_id}", "render_label": False}
                    asset_list = f"{asset_id}"

                    headers = {
                        "Content-Type": "application/json",
                        "NVCF-INPUT-ASSET-REFERENCES": asset_list,
                        "NVCF-FUNCTION-ASSET-IDS": asset_list,
                        "Authorization": header_auth,
                    }

                    response = requests.post(nvai_url, headers=headers, json=inputs)
                    output_zip_file = os.path.join('uploads', 'output.zip')

                    with open(output_zip_file, 'wb') as out_zip:
                        out_zip.write(response.content)

                    # Extract ZIP file
                    with zipfile.ZipFile(output_zip_file, 'r') as z:
                        z.extractall('uploads')

                    result_files = os.listdir('uploads')

                    # Read the content of the .response file
                    response_file_content = ""
                    for file in result_files:
                        if file.endswith('.response'):
                            response_file_path = os.path.join('uploads', file)
                            with open(response_file_path, 'r') as response_file:
                                response_file_content = response_file.read()
                            break

                    # Redirect to result page with query parameters
                    result_url = f'/result?files={"&".join(result_files)}&response={requests.utils.quote(response_file_content)}'
                    self.send_response(302)
                    self.send_header('Location', result_url)
                    self.end_headers()

                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(bytes(str(e), 'utf-8'))
            else:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'No file uploaded')
        else:
            self.send_response(404)
            self.end_headers()

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd server on port {port}...')
    httpd.serve_forever()

if __name__ == "__main__":
    run()
