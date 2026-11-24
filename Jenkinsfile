
pipeline {
    agent any

    environment {
        IMAGE_NAME = "riuu1110/aws-cost-optimizer"
        IMAGE_TAG = "latest"
        LAMBDA_FUNCTION_NAME = "IntelligentCostOptimizer"
        AWS_REGION = "ap-south-1"
    }

    stages {

        stage('Checkout Code') {
            steps {
                git branch: 'main',
                    url: 'https://github.com/Riya-te/Intelligent-aws-cost-optimizer.git'
            }
        }

        stage('Setup Python') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    python -m pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Run Unit Tests') {
            steps {
                sh '''
                    . venv/bin/activate
                    python -m unittest discover -s tests -v
                '''
            }
        }

        stage('Python Compilation') {
            steps {
                sh '''
                    . venv/bin/activate
                    python -m compileall -q src dashboard tests
                '''
            }
        }

        stage('SonarQube Scan') {
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'

                    withSonarQubeEnv('SonarQube') {
                        sh """
                            ${scannerHome}/bin/sonar-scanner
                        """
                    }
                }
            }
        }

        stage('Test Jenkins Shell') {
            steps {
                sh '''
                    echo "JENKINS PIPELINE SHELL OK"
                    sleep 5
                    echo "SHELL TEST COMPLETED"
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
                '''
            }
        }

        stage('Trivy Image Scan') {
            steps {
                sh '''
                    trivy image \
                        --severity HIGH,CRITICAL \
                        --ignore-unfixed \
                        --exit-code 1 \
                        ${IMAGE_NAME}:${IMAGE_TAG}
                '''
            }
        }

        stage('Push Docker Image') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {
                    sh '''
                        echo "$DOCKER_PASS" | docker login \
                            -u "$DOCKER_USER" --password-stdin

                        docker push ${IMAGE_NAME}:${IMAGE_TAG}

                        docker logout
                    '''
                }
            }
        }

        // NEW STAGE 1: Package Lambda
        stage('Package Lambda') {
            steps {
                sh '''
                    set -e

                    rm -rf lambda_package dist
                    mkdir -p lambda_package dist

                    . venv/bin/activate

                    python -m pip install \
                        --no-compile \
                        --no-cache-dir \
                        --target lambda_package \
                        -r lambda_requirements.txt

                    cp -r src lambda_package/src

                    find lambda_package -type d \
                        -name __pycache__ -prune -exec rm -rf {} +

                    find lambda_package -type f \
                        -name "*.pyc" -delete

                    python -c 'import os,zipfile; root="lambda_package"; z=zipfile.ZipFile("dist/IntelligentCostOptimizer.zip","w",zipfile.ZIP_DEFLATED); [z.write(os.path.join(d,f),os.path.relpath(os.path.join(d,f),root)) for d,ds,fs in os.walk(root) for f in fs]; z.close(); print("Lambda ZIP created successfully")'

                    python -c 'import zipfile; z=zipfile.ZipFile("dist/IntelligentCostOptimizer.zip"); n=z.namelist(); assert z.testzip() is None; assert "src/lambda_function.py" in n; assert any(x.startswith("boto3/") for x in n); print("ZIP validation passed:",len(n),"files")'
                '''
            }
        }

        // NEW STAGE 2: Deploy Lambda
        stage('Deploy Lambda') {
            steps {
                sh '''
                    set -e

                    aws lambda update-function-code \
                        --function-name ${LAMBDA_FUNCTION_NAME} \
                        --zip-file fileb://dist/IntelligentCostOptimizer.zip \
                        --region ${AWS_REGION}
                '''
            }
        }

        // NEW STAGE 3: Verify Lambda
        stage('Verify Lambda') {
            steps {
                sh '''
                    set -e

                    echo "Waiting for Lambda update..."

                    for i in $(seq 1 30); do

                        STATUS=$(aws lambda get-function-configuration \
                            --function-name ${LAMBDA_FUNCTION_NAME} \
                            --region ${AWS_REGION} \
                            --query 'LastUpdateStatus' \
                            --output text)

                        if [ "$STATUS" = "Successful" ]; then
                            break
                        fi

                        if [ "$STATUS" = "Failed" ]; then
                            echo "Lambda update failed"
                            exit 1
                        fi

                        sleep 5
                    done

                    if [ "$STATUS" != "Successful" ]; then
                        echo "Lambda update timed out"
                        exit 1
                    fi

                    STATE=$(aws lambda get-function-configuration \
                        --function-name ${LAMBDA_FUNCTION_NAME} \
                        --region ${AWS_REGION} \
                        --query 'State' \
                        --output text)

                    echo "Lambda State: $STATE"
                    echo "Lambda Update Status: $STATUS"

                    test "$STATE" = "Active"

                    echo "Lambda deployment verified successfully."
                '''
            }
        }
    }

    post {
        success {
            echo 'CI/CD pipeline and Lambda deployment completed successfully.'
        }

        failure {
            echo 'Pipeline failed. Check the failed stage logs.'
        }

        always {
            cleanWs()
        }
    }
}
