FROM python:3.9.12-slim-bullseye

RUN apt update -yq && apt install -y \
  git \
  cmake \
  python3.9 \
  python3-pip \
  libpython3-dev \
  libboost-all-dev

WORKDIR /app

COPY ./requirements.txt requirements.txt
RUN pip3 install --upgrade pip
RUN pip install -r requirements.txt

COPY ./src ./src
COPY ./lib ./lib
COPY ./viz3 ./viz3
COPY ./examples ./examples
COPY ./scripts ./scripts
COPY ./CMakeLists.txt .
COPY ./README.md .
COPY ./setup.py .

RUN mkdir -p build
WORKDIR /app/build
RUN cmake -DPYBIND11_PYTHON_VERSION=3.9 ..

RUN make install -j4
RUN python3.9 ../setup.py install

WORKDIR /app/examples
ENV PYTHON=python3.9
EXPOSE 8493
CMD [ "make", "-e", "machine_room_simple" ]
