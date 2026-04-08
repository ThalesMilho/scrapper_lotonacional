from http.server import BaseHTTPRequestHandler, HTTPServer
import json

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        print("\n" + "="*40)
        print("🎯 WEBHOOK RECEBIDO COM SUCESSO!")
        print("="*40)
        print("🔐 Headers (Verifique se a API Key está aqui):")
        for key, value in self.headers.items():
            if key in ['Authorization', 'Content-Type']:
                print(f"  {key}: {value}")
                
        print("\n📦 Payload (Os dados do jogo):")
        try:
            dados = json.loads(post_data.decode('utf-8'))
            print(json.dumps(dados, indent=2, ensure_ascii=False))
        except Exception:
            print(post_data.decode('utf-8'))
        print("="*40 + "\n")
        
        # Responde com 200 OK para o seu scraper saber que deu certo
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Recebido pelo Mock Server!")

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8000), WebhookHandler)
    print("Mock Server a escutar na porta 8000...")
    print("A aguardar que o microserviço envie os resultados...")
    server.serve_forever()