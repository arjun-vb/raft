import rsa
import os

for i in range(1, 6):
	public_key, private_key = rsa.newkeys(1024)
	filename = os.path.join(os.getcwd(), 'keys/pub'+str(i)+'.pem')
	print(filename)
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	with open(filename, "w") as f:
		f.write(public_key.save_pkcs1().decode('utf-8'))
		f.close()

	filename = os.path.join(os.getcwd(), 'keys/pvt'+str(i)+'.pem')
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	with open(filename, "w") as f:
		f.write(private_key.save_pkcs1().decode('utf-8'))
		f.close()