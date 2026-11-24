
pipeline {
    agent any

    environment {
        IMAGE_NAME = "riuu1110/aws-cost-optimizer"
        IMAGE_TAG = "latest"
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
    }

    post {
        success {
            echo 'CI/CD pipeline completed successfully.'
        }

        failure {
            echo 'Pipeline failed. Check the failed stage logs.'
        }

        always {
            cleanWs()
        }
    }
}
