#!/bin/bash

SLAVE_CONTAINER_ID=`docker ps -f name=backend_db_mysql-slave --format "{{.ID}}"`
DATETIME=`date +"%Y-%m-%d_%I:%M_%p"`
OUTPUT=./$DATETIME.backend_db.sql
FTP_SERVER='144.76.45.150'
FTP_USER='mg1385'
FTP_PASSWORD='i3fT86rN6r'
BACKEND_BACKUP_DIR='/backup/backend_db'

echo "Starting export..."
docker exec $SLAVE_CONTAINER_ID /usr/bin/mysqldump -u root -ppNFdaJuhQmhoMyzqbqnnrfSfZA1FlRwPb3kBGn8u cashbox_db > $OUTPUT
echo "Export finished"

echo "Uploading file into backup host"

lftp -u $FTP_USER,$FTP_PASSWORD -e "set ftp:ssl-allow no;cd $BACKEND_BACKUP_DIR;put $OUTPUT;exit" $FTP_SERVER
# ftp -n $FTP_SERVER <<End-Of-Session
# user $FTP_USER "$FTP_PASSWORD"
# binary
# cd $BACKEND_BACKUP_DIR
# put "$OUTPUT"
# bye
# End-Of-Session
echo "Upload finished"

echo "Cleaning junk files"
# clean after upload
rm -rf $OUTPUT
