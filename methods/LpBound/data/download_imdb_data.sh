#!/bin/bash

# download the data
wget https://event.cwi.nl/da/job/imdb.tgz
mv imdb.tgz imdb/
tar zxvf imdb/imdb.tgz -C imdb
rm imdb/imdb.tgz
