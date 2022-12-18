CC = gcc

SRCDIR = src
OBJDIR = obj
BINDIR = bin
INCLUDEDIR = include
DUMPSDIR = dumps
RECVDIR = recvfiles

CFLAGS = -std=gnu99 -g -O3 -I$(INCLUDEDIR)
LFLAGS = -lm -pthread

INCLUDE = $(INCLUDEDIR)/*.h

OBJ = $(OBJDIR)/handle.o \
      $(OBJDIR)/ring_buffer.o

default: all

all: $(BINDIR)/tinytcp | $(DUMPSDIR) $(RECVDIR)

$(DUMPSDIR):
	mkdir -p $@
	
$(RECVDIR):
	mkdir -p $@

$(OBJDIR)/%.o: $(SRCDIR)/%.c $(INCLUDE) | $(OBJDIR)
	$(CC) -c -o $@ $< $(CFLAGS)

$(OBJDIR):
	mkdir -p $@

$(BINDIR)/%: $(OBJDIR)/%.o $(OBJ) | $(BINDIR)
	$(CC) -o $@ $^ $(LFLAGS)

$(BINDIR):
	mkdir -p $@


.PRECIOUS: $(OBJDIR)/%.o

.PHONY: default all clean

clean:
	rm -r $(OBJDIR); rm -r $(BINDIR); rm -r $(DUMPSDIR); rm -r $(RECVDIR);
