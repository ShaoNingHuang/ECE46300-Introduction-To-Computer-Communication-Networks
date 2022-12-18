/* The code is subject to Purdue University copyright policies.
 * DO NOT SHARE, DISTRIBUTE, OR POST ONLINE
 */

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <sys/select.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netdb.h>
#include <arpa/inet.h>

#define LISTEN_QUEUE 50 /* Max outstanding connection requests; listen() param */
#define MYPORT 9015
#define DBPORT 54015
#define DBADDR "127.0.0.1"

int main(int argc, char *argv[])
{
    if (argc != 3) {
        fprintf(stderr, "usage: ./http_server [server port] [DB port]\n");
        exit(1);
    }

    int sockfd, new_fd;
	struct sockaddr_in my_addr;
	struct sockaddr_in their_addr; /* client's address info */
	int sin_size;
    sin_size = sizeof(struct sockaddr_in);
	char dst[INET_ADDRSTRLEN];
    if ((sockfd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
		perror("socket");
		exit(1);
	}

    my_addr.sin_family = AF_INET;
	my_addr.sin_port = htons(MYPORT);
	my_addr.sin_addr.s_addr = INADDR_ANY; /* bind to all local interfaces */
	bzero(&(my_addr.sin_zero), 8);

    if (bind(sockfd, (struct sockaddr *) &my_addr, sizeof(struct sockaddr_in)) < 0) {
		perror("bind");
		exit(1);
	}

    if (listen(sockfd, LISTEN_QUEUE) < 0) {
		perror("listen");
		exit(1);
	}
    while (1) {
        if ((new_fd = accept(sockfd, (struct sockaddr *) &their_addr,(socklen_t*) &sin_size)) < 0) {
			perror("accept");
			continue;
		}
        inet_ntop(AF_INET, &(their_addr.sin_addr), dst, INET_ADDRSTRLEN);
        
        char request[30000] = {'\0'};
        int bytes;
        bytes = recv(new_fd, request, 30000, 0);
        if (bytes) {
            char* method = strtok(request, " ");
            char* uri = strtok(NULL, " ");
            char* protocol = strtok(NULL, "\r\n");
            if (strstr(method, "GET") == NULL){ 
                fprintf(stdout,"%s \"%s %s %s\" 501 Not Implemented\n", dst, method, uri, protocol);
                char* response = "HTTP/1.0 501 Not Implemented\r\n\r\n<html><body><h1>501 Not Implemented</h1></body></html>";
                if (send(new_fd, response, strlen(response), 0) < 0) {
                perror("send");
                exit(1);
                }
            }
            if(strstr(protocol, "HTTP/1.0") == NULL && strstr(protocol, "HTTP/1.1") == NULL) {
                fprintf(stdout,"%s \"%s %s %s\" 501 Not Implemented\n", dst, method, uri, protocol);
                char* response = "HTTP/1.0 501 Not Implemented\r\n\r\n<html><body><h1>501 Not Implemented</h1></body></html>";
                if (send(new_fd, response, strlen(response), 0) < 0) {
                perror("send");
                exit(1);
                }
            }
            if (uri[0] != '/') {
                fprintf(stdout,"%s \"%s %s %s\" 400 Bad Request\n", dst, method, uri, protocol);
                char* response = "HTTP/1.0 400 Bad Request\r\n\r\n<html><body><h1>400 Bad Request</h1></body></html>";
                if (send(new_fd, response, strlen(response), 0) < 0) {
                perror("send");
                }
            }
            else  if (strstr(uri, "/../") != NULL) {
                fprintf(stdout,"%s \"%s %s %s\" 400 Bad Request\n", dst, method, uri, protocol);
                char* response = "HTTP/1.0 400 Bad Request\r\n\r\n<html><body><h1>400 Bad Request</h1></body></html>";
                if (send(new_fd, response, strlen(response), 0) < 0) {
                perror("send");
                }
            }
            else {
                char* malend = "/..";
                int lenofuri = strlen(uri);
                int lenofmalend = strlen(malend);
                int endwith = 0;
                if (lenofmalend <= lenofuri) {
                    for (int i = 0; i < lenofmalend; i++) {
                        if (uri[i + lenofuri - lenofmalend] != malend[i]) {
                            endwith = 0;
                            break;
                        }
                        endwith = 1;
                    }
                }
                if (endwith) {
                    fprintf(stdout,"%s \"%s %s %s\" 400 Bad Request\n", dst, method, uri, protocol);
                    char* response = "HTTP/1.0 400 Bad Request\r\n\r\n<html><body><h1>400 Bad Request</h1></body></html>";
                    if (send(new_fd, response, strlen(response), 0) < 0) {
                    perror("send");
                    }
                }
                else {
                    char new_uri[1000] = {'\0'};
                    strcpy(new_uri, uri);
                    //check last char
                    if (uri[strlen(uri) - 1] == '/') {
                        strcat(new_uri, "index.html");
                    }
                    //check if is dir
                    struct stat statbuf;
                    int isdir;
                    char Path[1000] = "Webpage";
                    strcat(Path, new_uri);
                    if (stat(Path, &statbuf) != 0) { isdir = 0;}
                    isdir = S_ISDIR(statbuf.st_mode);
                    if (isdir) {
                        if (new_uri[strlen(new_uri) - 1] != '/'){
                        strcat(Path, "/index.html");
                        }
                    }
                    FILE* fp = fopen(Path, "r");
                    if (fp) {
                        fprintf(stdout,"%s \"%s %s %s\" 200 OK\n", dst, method, uri, protocol);
                        int size = 0;
                        fseek(fp, 0, SEEK_END);
                        size = ftell(fp);
                        fseek(fp, 0, SEEK_SET);
                        char header[1000] = {'\0'};
                        sprintf(header, "HTTP/1.0 200 OK\r\nContent-Length: %d\r\n\r\n", size);
                        char firstdata[4096] = {0};
                        int lenofheader = strlen(header);
                        strcpy(firstdata, header);
                        char* ptr = firstdata + lenofheader;
                        int numread = fread(ptr, 1, 4096 - lenofheader, fp);
                        if (send(new_fd, firstdata, 4096, 0) < 0) {
                            perror("send");
                        }
                        size = size - numread;
                        int numofcount = 0;
                        while (numofcount < size) {
                            char restdata[4096] = {'\0'};
                            numofcount += fread(restdata, 1, 4096, fp);
                            if (send(new_fd, restdata, 4096, 0) < 0) {
                                perror("send");
                            }
                            usleep(10000);
                        }
                        fclose(fp);
                    }
                    else {
                        if (strstr(uri, "?key=") != NULL){
                            
                            char searchname [1000] = {'\0'};
                            strcpy(searchname, uri);
                            char* startofname = strstr(searchname, "=") + 1;
                            for (int i = 0; i < strlen(startofname); i++) {
                                if (startofname[i] == '+') {
                                    startofname[i] = ' ';
                                }
                            }
                            int newsockfd;
                            char buffer[4096] = {'\0'};
                            struct sockaddr_in dbaddr;

                            if ((newsockfd = socket(AF_INET, SOCK_DGRAM, 0)) < 0) {
		                        perror("socket");
		                        exit(1);
	                        }
                            int flags = fcntl(newsockfd, F_GETFL, 0) | O_NONBLOCK;
                            fcntl(newsockfd, F_SETFL, flags);

                            memset(&dbaddr, 0, sizeof(dbaddr));
                            dbaddr.sin_family = AF_INET;
                            dbaddr.sin_port = htons(DBPORT);
                            inet_pton(AF_INET, "127.0.0.1", &(dbaddr.sin_addr));
                            bzero(&(their_addr.sin_zero), 8);

                            int numbytes;
                            if((numbytes = sendto(newsockfd, startofname, strlen(startofname), 0,(struct sockaddr *) &dbaddr, sizeof(struct sockaddr))) < 0) {
		                        perror("sendto");
		                        exit(1);
	                        }

                            int addr_len = sizeof(struct sockaddr);
                            int NeedtoSendHeader = 1;
                            struct timeval timeout;
                            timeout.tv_sec = 5;
                            timeout.tv_usec = 0;
                            fd_set rfds;
                            FD_ZERO(&rfds);
                            int NeedToSendHeader = 1;
                            while(1) {
                                FD_SET(newsockfd, &rfds);
                                int retval = select(newsockfd + 1, &rfds, 0, 0, &timeout);
                                if (retval) {
                                    if (FD_ISSET(newsockfd, &rfds)) {
                                        int bytes = recvfrom(newsockfd, buffer, 4096, 0, (struct sockaddr *) &dbaddr, (socklen_t*)&addr_len);
                                        if (strstr(buffer, "File Not Found") != NULL) {
                                            fprintf(stdout,"%s \"%s %s %s\" 404 Not Found\n", dst, method, uri, protocol);
                                            char* response = "HTTP/1.0 404 Not Found\r\n\r\n<html><body><h1>404 Not Found</h1></body></html>";
                                            timeout.tv_sec = 5;
                                            timeout.tv_usec = 0;
                                            if (send(new_fd, response, strlen(response), 0) < 0) {
                                                perror("send");
                                                exit(1);
                                            }
                                            break;        
                                        }
                                        else {
                                            if (strstr(buffer, "DONE") != NULL) {
                                                break;
                                            }
                                            if (NeedToSendHeader) {
                                                fprintf(stdout,"%s \"%s %s %s\" 200 OK\n", dst, method, uri, protocol);
                                                char* header = "HTTP/1.0 200 OK\r\n\r\n";
                                                if (send(new_fd, header, strlen(header), 0) < 0) {
                                                    perror("send");
                                                    exit(1);
                                                }
                                                NeedToSendHeader = 0;
                                            }
                                            if (send(new_fd, buffer, 4096, 0) < 0) {
                                                perror("send");
                                                exit(1);
                                            }
                                        }
                                    }
                                }
                                else {
                                        fprintf(stdout,"%s \"%s %s %s\" 408 Request Timeout\n", dst, method, uri, protocol);
                                        char* response = "HTTP/1.0 408 Request Timeout\r\n\r\n<html><body><h1>408 Request Timeout</h1></body></html>";
                                        timeout.tv_sec = 5;
                                        timeout.tv_usec = 0;
                                        if (send(new_fd, response, strlen(response), 0) < 0) {
                                            perror("send");
                                            exit(1);
                                        }
                                        break;
                                }
                            }
                            close(newsockfd);                                     
                        }
                        else {
                            fprintf(stdout,"%s \"%s %s %s\" 404 Not Found\n", dst, method, uri, protocol);
                            char* response = "HTTP/1.0 404 Not Found\r\n\r\n<html><body><h1>404 Not Found</h1></body></html>";
                            if (send(new_fd, response, strlen(response), 0) < 0) {
                            perror("send");
                            }
                        }
                    }
                }
            }
        }
        close(new_fd);
    }
    return 0;
}
