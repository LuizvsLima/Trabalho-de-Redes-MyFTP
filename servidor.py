import socket
import threading 
import sys
import os
import queue
import struct


#o ACK funciona como uma confirmação de recebimento para o servidor.
#ele evitar que o servidor envie o próximo pacote antes de ter certeza de que o anterior chegou.
#UDP:protocolo de comunicação na camada de transporte da internet. 
#Ele é conhecido por ser simples, rápido e "não confiável"

#definem o endereco e a porta do servidor
HOST = '172.30.27.81'
PORT = 12345
#garante que o servidor sempre terá uma pasta dedicada
PASTA_RAIZ_SERVIDOR = os.path.join(os.getcwd(), 'servidor_arquivos')
os.makedirs(PASTA_RAIZ_SERVIDOR, exist_ok=True)

# Armazenará os usuários e senhas
USUARIOS_VALIDOS = {}

#Ele armazena uma fila de mensagens para cada cliente,criando sessões de forma isolada.
clientes_ativos = {}
#segurança para threads,garante que um thread por vez acesse e modifique o dicionario
clientes_lock = threading.Lock()

#prepara o sistema para o login
def carregar_usuarios():
    #Lê o arquivo usuarios.txt e carrega as credenciais
    try:
        #para encontrar o arquivo nao importa o diretorio que ele esteja
        dir_do_script = os.path.dirname(os.path.abspath(__file__))
        caminho_completo_usuarios = os.path.join(dir_do_script, "usuarios.txt")

        #coloca os valores nas variaveis de usuario vindo de usuarios.txt
        with open(caminho_completo_usuarios, "r") as f:
            for linha in f:
                linha = linha.strip()
                if linha:
                    usuario, senha = linha.split(",")
                    USUARIOS_VALIDOS[usuario] = senha
        print("Usuários carregados com sucesso.")
    except FileNotFoundError:
        print("Erro: Arquivo 'usuarios.txt' não encontrado.")
        sys.exit()
    except Exception as e:
        print(f"Erro ao carregar usuários: {e}")
        sys.exit()

def enviar_arquivo(servidor_socket, endereco_cliente, caminho_arquivo, fila_comandos):
    #Envia um arquivo para o cliente usando pacotes numerados
    print(f"Iniciando envio de {caminho_arquivo} para {endereco_cliente}")
    id_pacote = 0
    try:
        with open(caminho_arquivo, "rb") as f:
            while True:
                dados_arquivo = f.read(1020)#le o arquivo em pedaços de 1020 bytes
                cabecalho = struct.pack(">I", id_pacote)#adiciona cabeçalho 4bytes,com id pacote
                pacote = cabecalho + dados_arquivo
                while True:#esse while lida com o reenvio,ele espera por um ACK,se n chegar ele reenvia
                    servidor_socket.sendto(pacote, endereco_cliente)
                    try:
                        ack_packet = fila_comandos.get(timeout=5.0)
                        ack_id = struct.unpack(">I", ack_packet)[0]
                        if ack_id == id_pacote:
                            print(f"Pacote {id_pacote} confirmado.")
                            break
                        else:
                            print(f"ACK errado: esperado {id_pacote}, recebido {ack_id}. Reenviando...")
                    except queue.Empty:
                        print(f"Timeout no pacote {id_pacote}, reenviando...")
                        continue
                id_pacote += 1
                if not dados_arquivo:
                    print("Arquivo enviado com sucesso!")
                    break
    except Exception as e:
        print(f"Erro no envio do arquivo: {e}")

def receber_arquivo_servidor(servidor_socket, endereco_cliente, nome_arquivo_local, fila_comandos):
    #Recebe um arquivo do cliente usando pacotes numerados
    print(f"Iniciando recebimento de {nome_arquivo_local} do cliente {endereco_cliente}")
    id_pacote_esperado = 0
    try:
        with open(nome_arquivo_local, "wb") as f:
            while True:#ela fica esperando um pacote de cliente na fila 
                dados_recebidos = fila_comandos.get(timeout=600)
                cabecalho = dados_recebidos[:4]
                dados_pacote = dados_recebidos[4:]
                try:
                    id_pacote_recebido = struct.unpack(">I", cabecalho)[0]#verifica o id do pacote 
                except struct.error:
                    continue
                if id_pacote_recebido == id_pacote_esperado:#se for esperado ele salva dados e envia um ack     
                    f.write(dados_pacote)
                    ack = struct.pack(">I", id_pacote_esperado)
                    servidor_socket.sendto(ack, endereco_cliente)
                    print(f"Pacote {id_pacote_esperado} recebido.")
                    if not dados_pacote:
                        print("Arquivo recebido com sucesso!")
                        break
                    id_pacote_esperado += 1
                else:#caso contrario 
                    ack = struct.pack(">I", id_pacote_esperado - 1)#envia o ack do ultimo pacote recebido aprovado 
                    servidor_socket.sendto(ack, endereco_cliente)
    except Exception as e:
        print(f"Erro no recebimento de arquivo: {e}")

def processar_comando(servidor_socket, endereco_cliente, mensagem, estado_cliente, fila_comandos):
    #Processa comandos MyFTP de um cliente
    #ela recebe um comando de texto e executa a ação correspondente
    partes = mensagem.split()
    if not partes:
        servidor_socket.sendto("Comando vazio.".encode(), endereco_cliente)
        return
    comando = partes[0].lower()

    if comando == "login":
        if len(partes) == 3:
            usuario, senha = partes[1], partes[2]
            if USUARIOS_VALIDOS.get(usuario) == senha:
                estado_cliente['autenticado'] = True
                resposta = "Login bem-sucedido."
            else:
                resposta = "Usuário ou senha incorretos."
        else:
            resposta = "Uso: login <usuario> <senha>"
        servidor_socket.sendto(resposta.encode(), endereco_cliente)
        return

    if not estado_cliente['autenticado']:#garante que a maioria dos comandos seja feita apos login
        servidor_socket.sendto("Você precisa fazer login primeiro.".encode(), endereco_cliente)
        return

    if comando == "ls":
        try:
            arquivos = os.listdir(estado_cliente['dir_atual'])
            resposta = "\n".join(arquivos) if arquivos else "Diretório vazio."
        except Exception as e:
            resposta = f"Erro: {e}"
        servidor_socket.sendto(resposta.encode(), endereco_cliente)

    elif comando == "cd":#para comandos como cd mkdir foi usado biblioteca "os"
                        #para garantir que o cliente nao saia da biblioteca raiz
        if len(partes) == 2:
            novo = os.path.normpath(os.path.join(estado_cliente['dir_atual'], partes[1]))
            if not novo.startswith(PASTA_RAIZ_SERVIDOR):
                resposta = "Acesso negado."
            elif os.path.isdir(novo):
                estado_cliente['dir_atual'] = novo
                resposta = f"Diretório alterado para {os.path.basename(novo)}."
            else:
                resposta = "Pasta não encontrada."
        else:
            resposta = "Uso: cd <nome_pasta>"
        servidor_socket.sendto(resposta.encode(), endereco_cliente)

    elif comando == "cd..":
        if estado_cliente['dir_atual'] == PASTA_RAIZ_SERVIDOR:
            resposta = "Já está na raiz."
        else:
            estado_cliente['dir_atual'] = os.path.dirname(estado_cliente['dir_atual'])
            resposta = "Voltou um diretório."
        servidor_socket.sendto(resposta.encode(), endereco_cliente)

    elif comando == "mkdir":
        if len(partes) == 2:
            caminho = os.path.join(estado_cliente['dir_atual'], partes[1])
            try:
                os.mkdir(caminho)
                resposta = "Pasta criada."
            except Exception as e:
                resposta = f"Erro: {e}"
        else:
            resposta = "Uso: mkdir <nome_pasta>"
        servidor_socket.sendto(resposta.encode(), endereco_cliente)

    elif comando == "rmdir":
        if len(partes) == 2:
            caminho = os.path.join(estado_cliente['dir_atual'], partes[1])
            try:
                os.rmdir(caminho)
                resposta = "Pasta removida."
            except Exception as e:
                resposta = f"Erro: {e}"
        else:
            resposta = "Uso: rmdir <nome_pasta>"
        servidor_socket.sendto(resposta.encode(), endereco_cliente)
    #put e get nao fazem transferencia em si,eles iniciam a operação 
    #eles chamam a função de transferencia apropiada 
    elif comando == "get":
        if len(partes) == 2:
            caminho = os.path.join(estado_cliente['dir_atual'], partes[1])
            if os.path.isfile(caminho):
                servidor_socket.sendto(f"Pronto para enviar {partes[1]}".encode(), endereco_cliente)
                enviar_arquivo(servidor_socket, endereco_cliente, caminho, fila_comandos)
            else:
                servidor_socket.sendto("Arquivo não encontrado.".encode(), endereco_cliente)
        else:
            servidor_socket.sendto("Uso: get <arquivo>".encode(), endereco_cliente)

    elif comando == "put":
        if len(partes) == 2:
            caminho = os.path.join(estado_cliente['dir_atual'], partes[1])
            if os.path.exists(caminho):
                servidor_socket.sendto("Arquivo já existe no servidor.".encode(), endereco_cliente)
            else:
                servidor_socket.sendto("Pronto para receber.".encode(), endereco_cliente)
                receber_arquivo_servidor(servidor_socket, endereco_cliente, caminho, fila_comandos)
        else:
            servidor_socket.sendto("Uso: put <arquivo>".encode(), endereco_cliente)

    else:
        servidor_socket.sendto("Comando desconhecido.".encode(), endereco_cliente)

#essa função execita uma thread separada para cada cliente
def handle_cliente(servidor_socket, endereco_cliente, fila_comandos):
    estado_cliente = {'autenticado': False, 'dir_atual': PASTA_RAIZ_SERVIDOR}
    print(f"Thread iniciada para {endereco_cliente}")
    try:
        #o loop fica esperando os comandos na sua fila(fila_comandos.get)
        while True:
            dados = fila_comandos.get(timeout=600)
            try:
                mensagem = dados.decode()
            except:
                mensagem = dados
            #a variavel estado cliente armazena se o cliente esta logado e em qual pasta ele esta
            processar_comando(servidor_socket, endereco_cliente, mensagem, estado_cliente, fila_comandos)
    except queue.Empty:
        print(f"Cliente {endereco_cliente} inativo.")
    finally:
        with clientes_lock:
            clientes_ativos.pop(endereco_cliente, None)
        print(f"Thread encerrada para {endereco_cliente}")


def main():
    carregar_usuarios()
    servidor_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    servidor_socket.bind((HOST, PORT))
    print(f"Servidor MyFTP em {HOST}:{PORT}")

    while True:#ponto de entrada de todos os pacotes
        try:
            dados, endereco = servidor_socket.recvfrom(1024)
            with clientes_lock:
                if endereco not in clientes_ativos:#usada para saber se é novo cliente
                    #se for se cria uma nova thread para esse cliente
                    fila = queue.Queue()
                    t = threading.Thread(target=handle_cliente, args=(servidor_socket, endereco, fila))
                    t.start()
                    clientes_ativos[endereco] = {"fila": fila}
            clientes_ativos[endereco]["fila"].put(dados)#pega pacote recebido e despacha para fila de mensagens
            #da thread do cliente correspondente 
        except KeyboardInterrupt:
            print("Servidor encerrado.")
            break
    servidor_socket.close()

if __name__ == "__main__":
    main()