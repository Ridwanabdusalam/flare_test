s = serialport('com11',19200);
configureTerminator(s,"CR");
flush(s);
pause(1.0);
writeline(s,'p 0 020')
pause(1.0)
readline(s)

clear s
