import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import socket
import struct
import os

#ta definindo localhost e porta do servidor
HOST_SERVIDOR = '172.30.27.81'
PORT_SERVIDOR = 12345
#função pra gerenciar a comunicação c o servidor e manipular os arquivos
class MyFTPClient:

    #cria o socket UDP pra comunicação
    def __init__(self):
        self.cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.cliente_socket.settimeout(5.0) #para não travar se o servidor n responder

    #fecha e libera recurso
    def fechar_conexao(self):
        self.cliente_socket.close()

    #manda os comandos em bytes
    def enviarcomando(self, comando: str):
        try:
            self.cliente_socket.sendto(comando.encode(), (HOST_SERVIDOR, PORT_SERVIDOR))
            resposta, _ = self.cliente_socket.recvfrom(1024) #resposta de ate 1024 bytes
            return resposta.decode() #retorna em string
        except socket.timeout:
            return "Erro: O servidor não respondeu."
        except Exception as e:
            return f"Erro: {e}"

    #cada função ta executando oq foi pedido no tp, ls, mkdir, rmdir, cd, cd.. etc...
    def fazer_login(self, usuario, senha):
        return self.enviarcomando(f"login {usuario} {senha}")

    def listararq(self):
        return self.enviarcomando("ls")

    def mudardir(self, pasta):
        return self.enviarcomando(f"cd {pasta}")

    def voltardir(self):
        return self.enviarcomando("cd..")

    def criardir(self, pasta):
        return self.enviarcomando(f"mkdir {pasta}")

    def removedir(self, pasta):
        return self.enviarcomando(f"rmdir {pasta}")

    #função de get
    #envia um get para o servidor, ai a cada pacote envia um ACK para confirmar os pacotes recebidos
    def baixar_arquivo(self, nome_arquivo_servidor):
        self.cliente_socket.sendto(f"get {nome_arquivo_servidor}".encode(), (HOST_SERVIDOR, PORT_SERVIDOR))
        
        try:
            resposta_texto, _ = self.cliente_socket.recvfrom(1024) #recebe a resposta
            resposta = resposta_texto.decode()
            if not resposta.startswith("Pronto para enviar"):
                return resposta
        except socket.timeout:
            return "Erro: servidor não respondeu a tempo."

        print(f"Iniciando download de {nome_arquivo_servidor}...")
        id_pacote_esperado = 0 #controla ordem dos pacotes 
        try:
            #abre em binario
            with open(nome_arquivo_servidor, "wb") as f:
                while True:
                    dados, _ = self.cliente_socket.recvfrom(1024)
                    cabecalho = dados[:4] #4 bytes para id
                    payload = dados[4:] #4 bytes para arquivo
                    id_pacote = struct.unpack(">I", cabecalho)[0] #converte bytes p int

                    if id_pacote == id_pacote_esperado:
                        f.write(payload)
                        ack = struct.pack(">I", id_pacote_esperado) #cria o ACK aq
                        self.cliente_socket.sendto(ack, (HOST_SERVIDOR, PORT_SERVIDOR)) #envia ACK aq
                        if not payload:
                            break
                        id_pacote_esperado += 1
                    else: #esse else é se o pacote tiver fora de ordem ai ele reenvia o ultimo pacote 
                        ack = struct.pack(">I", id_pacote_esperado - 1)
                        self.cliente_socket.sendto(ack, (HOST_SERVIDOR, PORT_SERVIDOR))
            return f"Download concluído: {nome_arquivo_servidor}"
        except Exception as e:
            return f"Erro no download: {e}"

    #comando put, envia o arquivo para o servidor
    def enviar_arquivo(self, nome_arquivo_local):
        if not os.path.isfile(nome_arquivo_local):
            return f"Erro: o arquivo '{nome_arquivo_local}' não foi encontrado localmente."

        #comando de envio para o servidor
        self.cliente_socket.sendto(f"put {os.path.basename(nome_arquivo_local)}".encode(),
                                   (HOST_SERVIDOR, PORT_SERVIDOR))
        
        try:
            #recebe a resposta incial
            resposta_texto, _ = self.cliente_socket.recvfrom(1024)
            resposta = resposta_texto.decode()
            if not resposta.startswith("Pronto para receber"):
                return resposta
        except socket.timeout:
            return "Erro: servidor não respondeu a tempo."

        print(f"Iniciando o upload de {nome_arquivo_local}...")
        id_pacote = 0
        try:

            #abre o arquivo local em leitura binaria
            with open(nome_arquivo_local, "rb") as f:
                while True:
                    payload = f.read(1020)
                    cabecalho = struct.pack(">I", id_pacote)
                    pacote = cabecalho + payload

                    #esse loop roda ate receber o ACK correto
                    while True:
                        self.cliente_socket.sendto(pacote, (HOST_SERVIDOR, PORT_SERVIDOR))
                        try:
                            ack, _ = self.cliente_socket.recvfrom(1024)
                            ack_id = struct.unpack(">I", ack)[0]
                            if ack_id == id_pacote:
                                break
                        except socket.timeout:
                            continue
                    id_pacote += 1
                    if not payload:
                        break
            return f"Upload concluído: {nome_arquivo_local}"
        except Exception as e:
            return f"Erro no upload: {e}"


class MyFTPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("My FTP")
        self.root.geometry("800x500")
        self.root.configure(bg="#2c2f48")
        # Instancia a classe do cliente real
        self.ftp = MyFTPClient()

        # TOPO: LOGIN
        top = tk.Frame(root, bg="#323559", pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Usuário:", bg="#323559", fg="white").pack(side="left", padx=(10,5))
        self.entry_user = tk.Entry(top, width=15)
        self.entry_user.pack(side="left", padx=5)

        tk.Label(top, text="Senha:", bg="#323559", fg="white").pack(side="left", padx=(10,5))
        self.entry_pass = tk.Entry(top, show="*", width=15)
        self.entry_pass.pack(side="left", padx=5)

        tk.Button(top, text="Entrar", command=self.login,
                  bg="#ff9800", fg="white", relief="flat", width=12).pack(side="left", padx=10)

        # CORPO
        container = tk.Frame(root, bg="#2c2f48")
        container.pack(expand=True, fill="both")

        # Esquerda - Menu
        left = tk.Frame(container, bg="#2c2f48")
        left.pack(side="left", fill="y", padx=10, pady=10)

        def mkbtn(text, cmd):
            return tk.Button(left, text=text, command=cmd,
                             bg="#3c3f63", fg="white",
                             activebackground="#50538a",
                             relief="flat", font=("Segoe UI", 10),
                             width=18, height=2)

        mkbtn("Listar (ls)", self.ls).pack(pady=4)
        mkbtn("Cd", self.cd).pack(pady=4)
        mkbtn("Cd..", self.cd_back).pack(pady=4)
        mkbtn("Mkdir", self.mkdir).pack(pady=4)
        mkbtn("Rmdir", self.rmdir).pack(pady=4)
        mkbtn("Upload (put)", self.put_file).pack(pady=8)
        mkbtn("Download (get)", self.get_file).pack(pady=4)
        mkbtn("Sair", self.sair).pack(pady=25)

        # Direita - Logs
        right = tk.Frame(container, bg="#1e1e2f")
        right.pack(side="right", expand=True, fill="both", padx=10, pady=10)

        tk.Label(right, text="Logs", fg="white", bg="#1e1e2f",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=6, pady=(6, 0))
        self.text_log = tk.Text(right, bg="black", fg="lime",
                                font=("Consolas", 10), insertbackground="white")
        self.text_log.pack(expand=True, fill="both", padx=6, pady=6)

    # Util
    def log(self, msg):
        self.text_log.insert(tk.END, msg + "\n")
        self.text_log.see(tk.END)

    # Funções FTP
    def login(self):
        user = self.entry_user.get().strip()
        senha = self.entry_pass.get().strip()
        if not user or not senha:
            messagebox.showwarning("Aviso", "Preencha usuário e senha")
            return
        # Usa o método real da classe MyFTPClient
        resp = self.ftp.fazer_login(user, senha)
        self.log("Servidor: " + resp)

    def ls(self): 
        self.log("Servidor: " + self.ftp.listararq())
    def cd(self):
        pasta = simpledialog.askstring("Cd", "Nome da pasta:")
        if pasta: self.log("Servidor: " + self.ftp.mudardir(pasta))
    def cd_back(self): 
        self.log("Servidor: " + self.ftp.voltardir())
    def mkdir(self):
        pasta = simpledialog.askstring("Mkdir", "Nome da pasta:")
        if pasta: self.log("Servidor: " + self.ftp.criardir(pasta))
    def rmdir(self):
        pasta = simpledialog.askstring("Rmdir", "Nome da pasta:")
        if pasta: self.log("Servidor: " + self.ftp.removedir(pasta))
    def put_file(self):
        caminho = filedialog.askopenfilename()
        if caminho:
            self.log("Cliente: enviando arquivo…")
            self.log("Servidor: " + self.ftp.enviar_arquivo(caminho))
    def get_file(self):
        nome = simpledialog.askstring("Get", "Nome do arquivo no servidor:")
        if nome:
            self.log("Cliente: baixando arquivo…")
            self.log("Servidor: " + self.ftp.baixar_arquivo(nome))
    def sair(self):
        try: self.ftp.fechar_conexao()
        finally: self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MyFTPApp(root)
    root.mainloop()