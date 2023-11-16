users_primary: ./bin/litefs mount -config ./users/etc/primary.yml
users_secondary_1: ./bin/litefs mount -config ./users/etc/secondary_1.yml
users_secondary_2: ./bin/litefs mount -config ./users/etc/secondary_2.yml
enroll_1: uvicorn --port $PORT enroll.api:app --reload
enroll_2: uvicorn --port $PORT enroll.api:app --reload
enroll_3: uvicorn --port $PORT enroll.api:app --reload
krakend: echo krakend.json | entr -nrz krakend run --port $PORT --config krakend.json
dynamodb_local: java -Djava.library.path=./bin/DynamoDBLocal_lib -jar ./bin/DynamoDBLocal.jar -sharedDb -port $PORT