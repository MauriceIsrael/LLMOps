On release 23.4 the element manager's bulk configuration export is capped at
2 000 managed objects per request and rejects concurrent exports on the same
node. In practice a full export of a core node takes three passes. Anyone
planning a nightly backup of the whole estate through that interface should size
for that, and should not assume the documented figure of 10 000.