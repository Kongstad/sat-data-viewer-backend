FROM public.ecr.aws/lambda/python:3.12

# Install system dependencies for rasterio
RUN dnf install -y \
    gcc \
    gcc-c++ \
    gdal \
    gdal-devel \
    && dnf clean all

# Copy requirements and install Python dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application code
COPY app/ ${LAMBDA_TASK_ROOT}/app/

# Set the CMD to your handler
CMD [ "app.main.handler" ]
