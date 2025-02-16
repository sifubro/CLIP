# Latest Update : 18 July 2022, 09:55 GMT+7
# From https://github.com/openai/CLIP/issues/83

'''
NOTE :
that for inference purpose, the conversion step from fp16 to fp32 is not needed, just use the model in full fp16
For multi-GPU training, see my comment on how to use multiple GPUs,the default is to use the first CUDA device #111 (comment)
I'm not the author of this model nor having any relationship with the author. I'm just a random guy who interested in CLIP.
For training image-image or text-text, please refer to this principle : CLIP Training Code #83 (comment)
What is the difference between image loss and text loss? isn't one just a transposed version of the other one? read this then CLIP Training Code #83 (comment)
Why the ground truth is torch.arange? CLIP Training Code #83 (comment)
Code to save the model :

torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict(),
        'loss': total_loss,
        }, f"model_checkpoint/model_10.pt") #just change to your preferred folder/filename
Code to load the saved model :

model, preprocess = clip.load("ViT-B/32",device=device,jit=False) #Must set jit=False for training
checkpoint = torch.load("model_checkpoint/model_10.pt")

# Use these 3 lines if you use default model setting(not training setting) of the clip. For example, if you set context_length to 100 since your string is very long during training, then assign 100 to checkpoint['model_state_dict']["context_length"] 
checkpoint['model_state_dict']["input_resolution"] = model.input_resolution #default is 224
checkpoint['model_state_dict']["context_length"] = model.context_length # default is 77
checkpoint['model_state_dict']["vocab_size"] = model.vocab_size 

model.load_state_dict(checkpoint['model_state_dict'])
Alternative training code :

@Zasder3 have created a PyTorch lighting version to train the CLIP https://github.com/Zasder3/train-CLIP
@mitchellnw researchers at UW, Google, Stanford, Amazon, Columbia, and Berkeley also create their training code https://github.com/mlfoundations/open_clip
'''

# TO ADD :
# Gradient Checkpointing
# Filter out bias from weight decay
# Decaying learning rate with cosine schedule
# Half-precision Adam statistics
# Half-precision stochastically rounded text encoder weights were used

#BATCH_SIZE must larger than 1

device = "cuda:0" if torch.cuda.is_available() else "cpu" # If using GPU then use mixed precision training.
model, preprocess = clip.load("ViT-B/32",device=device,jit=False) #Must set jit=False for training

class image_title_dataset(Dataset):
    def __init__(self, list_image_path,list_txt):

        self.image_path = list_image_path
        self.title  = clip.tokenize(list_txt) #you can tokenize everything at once in here(slow at the beginning), or tokenize it in the training loop.

    def __len__(self):
        return len(self.title)

    def __getitem__(self, idx):
        image = preprocess(Image.open(self.image_path[idx])) # Image from PIL module
        title = self.title[idx]
        return image,title

# use your own data
list_image_path = ['folder/image1.jpg','folder2/image2.jpg'] 
list_txt = ['description for image1.jpg' , 'description for image2.jpg']
dataset = image_title_dataset(list_image_path,list_txt)
train_dataloader = DataLoader(dataset,batch_size = BATCH_SIZE) #Define your own dataloader

#https://github.com/openai/CLIP/issues/57
def convert_models_to_fp32(model): 
    for p in model.parameters(): 
        p.data = p.data.float() 
        p.grad.data = p.grad.data.float() 


if device == "cpu":
  model.float()
else :
  clip.model.convert_weights(model) # Actually this line is unnecessary since clip by default already on float16

loss_img = nn.CrossEntropyLoss()
loss_txt = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=5e-5,betas=(0.9,0.98),eps=1e-6,weight_decay=0.2) #Params used from paper, the lr is smaller, more safe for fine tuning to new dataset

# add your own code to track the training progress.
for epoch in range(EPOCH):
  for batch in train_dataloader :
      optimizer.zero_grad()

      images,texts = batch 
    
      images= images.to(device)
      texts = texts.to(device)
    
      logits_per_image, logits_per_text = model(images, texts)

      ground_truth = torch.arange(len(images),dtype=torch.long,device=device)

      total_loss = (loss_img(logits_per_image,ground_truth) + loss_txt(logits_per_text,ground_truth))/2
      total_loss.backward()
      if device == "cpu":
         optimizer.step()
      else : 
        convert_models_to_fp32(model)
        optimizer.step()
        clip.model.convert_weights(model)