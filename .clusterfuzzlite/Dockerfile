FROM gcr.io/oss-fuzz-base/base-builder-python

COPY . $SRC/examples
COPY .clusterfuzzlite/build.sh $SRC/build.sh
WORKDIR $SRC/examples
