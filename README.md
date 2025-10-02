# Trabalho-de-Redes-MyFTP
# MyFTP - Protocolo de Transferencia de Arquivos Customizado

Projeto de um sistema de transferencia de arquivos chamado MyFTP, desenvolvido em Python para a disciplina de Redes de Computadores.
A comunicacao usa o protocolo UDP e possui dois modulos principais:

Servidor: escuta os clientes, processa comandos e gerencia arquivos.
Cliente: conecta ao servidor, envia comandos e possui interface grafica.

O servidor lida com multiplos clientes usando fork ou threads.

# Funcionalidades

login -> autentica usuarios (trabalho_redes/usuarios.txt)

put <arquivo> -> envia arquivo do cliente para o servidor

get <arquivo> -> baixa arquivo do servidor

ls -> lista arquivos do diretorio atual

cd <diretorio> -> entra em um diretorio

cd.. -> retorna ao diretorio anterior

mkdir <nome> -> cria novo diretorio

rmdir <nome> -> remove diretorio

Tratamento de erros (exemplo: arquivo inexistente)

# Tecnologias utilizadas

Python 3
UDP
Interface grafica


Autoria
Desenvolvido por Luiz Victor Silva Lima como trabalho da disciplina Redes de Computadores UFOP 2025
