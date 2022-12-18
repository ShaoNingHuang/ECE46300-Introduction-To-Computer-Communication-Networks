/* The code is subject to Purdue University copyright policies.
 * DO NOT SHARE, DISTRIBUTE, OR POST ONLINE
 */

#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <libgen.h>
#include <stdbool.h>

int checkResponse(char* buffer, int* content_length) {
    // Check the response status code
    int status_code;
    sscanf(buffer, "HTTP/1.1 %d ", &status_code);
    if (status_code != 200) {
        fprintf(stderr, "Error: %d\n", status_code);
        return 1;
    }

    // Get the content length
    char *content_length_str = strstr(buffer, "Content-Length: ");
    if (content_length_str) {
        sscanf(content_length_str, "Content-Length: %d\r\n", content_length);
    }
    else {
        fprintf(stderr, "Error: could not download the requested file (file length unknown)\n");
        return 1;
    }

    return 0;
}

int main(int argc, char *argv[])
{
    int sockfd, numbytes;
	struct sockaddr_in their_addr; /* client's address information */
	struct hostent* he;
    char str[1000];
    short portnum = atoi(argv[2]);
    char* filename = basename(argv[3]);
    FILE *fp = fopen(filename, "wb");
    if (fp == NULL) {
        fprintf(stderr, "Error opening the file %s", filename);
        return -1;
    }
    if (argc != 4) {
        fprintf(stderr, "usage: ./http_client [host] [port number] [filepath]\n");
        exit(1);
    }
    
    if ((he = gethostbyname(argv[1])) == NULL) {
		herror("gethostbyname");
		exit(1);
	}

    if ((sockfd = socket(AF_INET, SOCK_STREAM, 0)) < 0) {
		perror("socket");
		exit(1);
	}

    their_addr.sin_family = AF_INET;
	their_addr.sin_port = htons(portnum);
	their_addr.sin_addr = *((struct in_addr *)he->h_addr_list[0]);
	bzero(&(their_addr.sin_zero), 8);

    if (connect(sockfd, (struct sockaddr *) &their_addr,
    sizeof(struct sockaddr)) < 0) {
		perror("connect");
		exit(1);
	}

    fprintf(stderr, "socket successfully opened\n");
    char req_msg[100];
    sprintf(req_msg, "GET %s HTTP/1.1\r\nHost: %s:%s\r\n\r\n", argv[3], argv[1], argv[2]);
    //fprintf(stderr,"%s\n", req_msg);
    int msg_length = strlen(req_msg);
    if(send(sockfd, req_msg, msg_length, 0) < 0) {
        perror("send");
        exit(1);
    }
    //fprintf(stderr, "request sent\n");
    char header[100];
    int bytes_recv;
    char buffer[1024];
    size_t curr_size = 0;
    bool isContent = false;
    int contLen = 0;
    //getting response

    while ((bytes_recv = recv(sockfd, header, 1, 0))) {
        if (bytes_recv < 0) {
            perror("recv");
            exit(1);
        } 
        //fprintf(stderr,"%s", header);
        if (isContent == false) {
            buffer[curr_size++] = *header;
            char* content = strstr(buffer, "\r\n\r\n");
            if (content != NULL) {
                fprintf(stderr,"%s", buffer);
                if(checkResponse(buffer, &contLen) == 1) {
                    return 0;
                }
                isContent = true;
            }
        }
        else {
            //fprintf(stderr,"%s-----------------------------\n", header);
            if(contLen > 0) {
                fwrite(&header, sizeof(char), bytes_recv, fp);
                contLen--;
            }
            else {
                break;
            }
        }
    }

    close(sockfd);
    fclose(fp);
    return 0;
}



