import socket
import struct
import os

#socket é um intermedio do computador com a internet,ele faz o trafego
# Configurações do Cliente
HOST_SERVIDOR = '127.0.0.1'
PORT_SERVIDOR = 12345

class MyFTPClient:
    def __init__(self):
        self.cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Define um tempo limite para esperar respostas do servidor
        self.cliente_socket.settimeout(5.0)

    def fechar_conexao(self):
        #Fecha o socket do cliente
        self.cliente_socket.close()

    def enviar_comando_simples(self, comando: str):
        #Envia um comando de texto e espera uma resposta.
        try:
            self.cliente_socket.sendto(comando.encode(), (HOST_SERVIDOR, PORT_SERVIDOR))
            resposta, _ = self.cliente_socket.recvfrom(1024)
            return resposta.decode()
        except socket.timeout:
            return "Erro: O servidor não respondeu."
        except Exception as e:
            return f"Erro: {e}"

    # Comandos do Protocolo MyFTP
    def fazer_login(self, usuario, senha):
        #Comando de login
        return self.enviar_comando_simples(f"login {usuario} {senha}")

    def listar_arquivos(self):
        #Comando 'ls'
        return self.enviar_comando_simples("ls")

    def mudar_diretorio(self, pasta):
        #Comando 'cd'
        return self.enviar_comando_simples(f"cd {pasta}")

    def voltar_diretorio(self):
        #Comando 'cd..'
        return self.enviar_comando_simples("cd..")

    def criar_diretorio(self, pasta):
        #Comando 'mkdir'
        return self.enviar_comando_simples(f"mkdir {pasta}")

    def remover_diretorio(self, pasta):
        #Comando 'rmdir'
        return self.enviar_comando_simples(f"rmdir {pasta}")

    def baixar_arquivo(self, nome_arquivo_servidor):
        #Comando 'get': Recebe um arquivo do servidor.
        self.cliente_socket.sendto(f"get {nome_arquivo_servidor}".encode(), (HOST_SERVIDOR, PORT_SERVIDOR))
        
        # Espera a confirmação de que o servidor está pronto
        try:
            resposta_texto, _ = self.cliente_socket.recvfrom(1024)
            resposta = resposta_texto.decode()
            if not resposta.startswith("Pronto para enviar"):
                return resposta
        except socket.timeout:
            return "Erro: servidor não respondeu a tempo."

        print(f"Iniciando o download de {nome_arquivo_servidor}...")
        id_pacote_esperado = 0
        try:
            with open(nome_arquivo_servidor, "wb") as f:
                while True:
                    dados_recebidos, _ = self.cliente_socket.recvfrom(1024)
                    
                    cabecalho = dados_recebidos[:4]
                    payload = dados_recebidos[4:]
                    id_pacote_recebido = struct.unpack(">I", cabecalho)[0]

                    if id_pacote_recebido == id_pacote_esperado:
                        f.write(payload)
                        ack = struct.pack(">I", id_pacote_esperado)
                        self.cliente_socket.sendto(ack, (HOST_SERVIDOR, PORT_SERVIDOR))
                        if not payload:
                            break
                        id_pacote_esperado += 1
                    else:
                        ack = struct.pack(">I", id_pacote_esperado - 1)
                        self.cliente_socket.sendto(ack, (HOST_SERVIDOR, PORT_SERVIDOR))
            return f"Download concluído: {nome_arquivo_servidor}"
        except Exception as e:
            return f"Erro no download: {e}"

    def enviar_arquivo(self, nome_arquivo_local):
        #Comando 'put': Envia um arquivo para o servidor
        if not os.path.isfile(nome_arquivo_local):
            return f"Erro: O arquivo '{nome_arquivo_local}' não foi encontrado localmente."

        self.cliente_socket.sendto(f"put {os.path.basename(nome_arquivo_local)}".encode(),
                                   (HOST_SERVIDOR, PORT_SERVIDOR))
        
        # Espera a confirmação de que o servidor está pronto
        try:
            resposta_texto, _ = self.cliente_socket.recvfrom(1024)
            resposta = resposta_texto.decode()
            if not resposta.startswith("Pronto para receber"):
                return resposta
        except socket.timeout:
            return "Erro: servidor não respondeu a tempo."

        print(f"Iniciando o upload de {nome_arquivo_local}...")
        id_pacote = 0
        try:
            with open(nome_arquivo_local, "rb") as f:
                while True:
                    payload = f.read(1020)
                    cabecalho = struct.pack(">I", id_pacote)
                    pacote = cabecalho + payload

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



# Lógica de Execução via Terminal

def main():
    cliente = MyFTPClient()
    print("Cliente MyFTP iniciado. Digite 'sair' para fechar.")

    while True:
        try:
            entrada = input("> ").strip()
            if not entrada:
                continue
            if entrada.lower() == "sair":
                break

            partes = entrada.split()
            comando = partes[0].lower()

            if comando == "login" and len(partes) == 3:
                print(cliente.fazer_login(partes[1], partes[2]))
            elif comando == "ls":
                print(cliente.listar_arquivos())
            elif comando == "cd" and len(partes) == 2:
                print(cliente.mudar_diretorio(partes[1]))
            elif comando == "cd..":
                print(cliente.voltar_diretorio())
            elif comando == "mkdir" and len(partes) == 2:
                print(cliente.criar_diretorio(partes[1]))
            elif comando == "rmdir" and len(partes) == 2:
                print(cliente.remover_diretorio(partes[1]))
            elif comando == "get" and len(partes) == 2:
                print(cliente.baixar_arquivo(partes[1]))
            elif comando == "put" and len(partes) == 2:
                print(cliente.enviar_arquivo(partes[1]))
            else:
                print("Comando inválido ou sintaxe incorreta.")

        except Exception as e:
            print(f"Erro no cliente: {e}")
            break

    cliente.fechar_conexao()
    print("Conexão encerrada.")

if __name__ == "__main__":
    main()