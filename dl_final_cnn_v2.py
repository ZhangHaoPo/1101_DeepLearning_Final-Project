
from google.colab import drive
drive.mount('/content/drive')

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
import matplotlib.pyplot as plt
import torch.utils.data as Data
from torch.utils.data import Dataset, TensorDataset, DataLoader
from torch.utils.data.dataset import random_split
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import f_regression
from sklearn.model_selection import train_test_split

# 讀資料看一下資料長怎樣
# 處理全部為0


df = pd.read_csv('/content/drive/MyDrive/DL/Final Project/Darknet.csv')

# print(((df == 0).all() == True).sum())
# df.describe()
# print(pd.unique(df["Fwd Bytes/Bulk Avg"]))

# Fwd Bytes/Bulk Avg, Fwd Packet/Bulk Avg, Fwd Bulk Rate Avg, Bwd Bytes/Bulk Avg, Subflow Bwd Packets, Active Mean, Active Std, Active Max, Active Min, URG Flag Count, CWE Flag Count, ECE Flag Count, Bwd URG Flags, Fwd URG Flags, Bwd PSH Flags都是 0
# 所以drop掉
print(df[df.Label1 == 'Non-Tor'].shape[0])
print(df[df.Label1 == 'NonVPN'].shape[0])
print(df[df.Label1 == 'Tor'].shape[0])
print(df[df.Label1 == 'VPN'].shape[0])
df = df.drop(columns={"Fwd Bytes/Bulk Avg", "Fwd Packet/Bulk Avg", "Fwd Bulk Rate Avg", "Bwd Bytes/Bulk Avg", "Subflow Bwd Packets", "Active Mean", "Active Std", "Active Max", "Active Min", "URG Flag Count", "CWE Flag Count", "ECE Flag Count", "Bwd URG Flags", "Fwd URG Flags", "Bwd PSH Flags"})

print(((df == 0).all() == True).sum())

# 處理NaN值

df_check_nan = df.columns[df.isna().any()].tolist() 
print(df_check_nan) #['Flow Bytes/s'] 有NaN

# ['Flow Bytes/s'] NaN 替換為 (Total Length of Fwd Packet + Total Length of Bwd Packet) / (Flow Duration * 10^-6)
# df["Flow Bytes/s"].fillna( (df["Total Length of Fwd Packet"] + df["Total Length of Bwd Packet"]) / (df["Flow Duration"] * 10^-6) , inplace=True)
# 這樣一樣會有NaN 可能問題出在分母或者分子出現0 所以改用整個Column的mean下去計算
# df["Flow Bytes/s"].fillna((df["Total Length of Fwd Packet"].mean() + df["Total Length of Bwd Packet"].mean() ) / (df["Flow Duration"].mean() * 0.000001), inplace=True ) 
print(df["Flow Bytes/s"].isna().sum())
df["Flow Bytes/s"].fillna( (df["Total Length of Fwd Packet"].mean() + df["Total Length of Bwd Packet"].mean()) / (df["Flow Duration"].mean() * 0.000001) , inplace=True)

# [Flow Packets/s] Inf 替換成 Fwd Packets/s + Bwd Packets/s
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df["Flow Packets/s"].fillna( df["Fwd Packets/s"] + df["Bwd Packets/s"] , inplace=True)

print(df["Flow Bytes/s"].isna().sum()) #阿怎麼還有2個啦 wt.....

# Encoging Label
print(pd.unique(df["Label1"])) # ['Non-Tor' 'NonVPN' 'Tor' 'VPN']
print(pd.unique(df["Label2"])) # ['AUDIO-STREAMING' 'Browsing' 'Chat' 'Email' 'File-Transfer''File-transfer' 'P2P' 'Video-Streaming' 'Audio-Streaming' 'Video-streaming' 'VOIP']

# 因為paper裡面有說有只有8個 裡面有大小寫但是是一樣的東西
df = df.replace({'Label2':{"Audio-Streaming": "AUDIO-STREAMING", "Video-streaming": "Video-Streaming", "File-transfer": "File-Transfer"}})

# print(pd.unique(df["Label2"])) #['AUDIO-STREAMING' 'Browsing' 'Chat' 'Email' 'File-Transfer' 'P2P' 'Video-Streaming' 'VOIP']
df = df.replace({'Label1':{"VPN": 0, "Tor": 1, "Non-Tor": 2, "NonVPN": 3}})
df = df.replace({'Label2':{"AUDIO-STREAMING" : 0, "Browsing" : 1, "Chat" : 2, "Email" : 3, "File-Transfer" : 4, "P2P" : 5, "Video-Streaming" : 6, "VOIP" : 7}})

print(pd.unique(df["Label1"]))
print(pd.unique(df["Label2"]))

# 處理IP位置 切成四部分

# print(len(df.columns))
df[['Src IP1','Src IP2','Src IP3','Src IP4']] = df["Src IP"].str.split('.', expand=True)
df[['Dst IP1','Dst IP2','Dst IP3','Dst IP4']] = df["Dst IP"].str.split('.', expand=True)

# 原先的Dst 跟 Src IP就不要了，Flow IP類似Socket概念但欄位有包含來源端目的端的IP跟Port所以就drop掉
df = df.drop(columns={"Src IP","Dst IP", "Flow ID"})

df["Dst IP4"] = df["Dst IP4"].astype(int)
df["Dst IP3"] = df["Dst IP3"].astype(int)
df["Dst IP2"] = df["Dst IP2"].astype(int)
df["Dst IP1"] = df["Dst IP1"].astype(int)
df["Src IP1"] = df["Src IP1"].astype(int)
df["Src IP2"] = df["Src IP2"].astype(int)
df["Src IP3"] = df["Src IP3"].astype(int)
df["Src IP4"] = df["Src IP4"].astype(int)

# Convert Time 
# Features 很多直接先Drop掉試看看
df = df.drop(["Timestamp"], axis = 1)

df["Flow Bytes/s"].fillna( (df["Total Length of Fwd Packet"].mean() + df["Total Length of Bwd Packet"].mean()) / (df["Flow Duration"].mean() * 0.000001) , inplace=True)
df_check_nan2 = df.columns[df.isna().any()].tolist() 
print(df_check_nan2) #['Flow Bytes/s'] 無NaN

x_split = df

# Select Features(72 -> 64)
# print(len(df.columns)) # 72

# 先把Label subframe切開 (Label 不用做z-scale)
y1 = df['Label1']
y2 = df['Label2']

# print(y1.shape) # (141530,)
# print(y2.shape) # (141530,)

df = df.drop(columns={"Label1", "Label2"})

x = df

# Z-Scale
scale = StandardScaler() #z-scaler
df = pd.DataFrame(scale.fit_transform(df),columns=df.keys())


# P-value select features
fr = f_regression(x, y1)[1]
# print(df.columns[fr > 0.05]) #['Total Bwd packets', 'Fwd Packet Length Mean', 'Bwd Header Length', 'Packet Length Max', 'Down/Up Ratio', 'Fwd Segment Size Avg', 'FWD Init Win Bytes', 'Dst IP1']

# 根據經驗的話Dst IP不能Drop掉
# print(df.columns[fr > 0.03]) #多'Bwd IAT Total'
df = df.drop(columns={'Total Bwd packets', 'Fwd Packet Length Mean', 'Bwd IAT Total', 'Bwd Header Length', 'Packet Length Max', 'Down/Up Ratio', 'Fwd Segment Size Avg', 'FWD Init Win Bytes', })

x_split = x_split.drop(columns={'Total Bwd packets', 'Fwd Packet Length Mean', 'Bwd IAT Total', 'Bwd Header Length', 'Packet Length Max', 'Down/Up Ratio', 'Fwd Segment Size Avg', 'FWD Init Win Bytes', })

train = x_split.sample(frac=0.8,random_state=200) #random state is a seed value
test = x_split.drop(train.index)
print(len(train['Label1']))
print(len(test['Label1']))

# Train to numpy
label_1_train = train['Label1']
label_2_train = train['Label2']
data_train =  train.drop(columns={'Label1', 'Label2'})

# Z-Scale
scale = StandardScaler() #z-scaler
data_train = pd.DataFrame(scale.fit_transform(data_train),columns=data_train.keys())



label_1_train = pd.DataFrame.to_numpy(label_1_train)
label_2_train = pd.DataFrame.to_numpy(label_2_train)
data_train = pd.DataFrame.to_numpy(data_train)

plt.imshow(data_train[54231].reshape(8,8))
plt.show()


# Test
label_1_test = test['Label1']
label_2_test = test['Label2']
data_test =  test.drop(columns={'Label1', 'Label2'})


data_test = pd.DataFrame(scale.fit_transform(data_test),columns=data_test.keys())

label_1_test = pd.DataFrame.to_numpy(label_1_test)
label_2_test = pd.DataFrame.to_numpy(label_2_test)
data_test = pd.DataFrame.to_numpy(data_test)


data_train = torch.from_numpy(data_train).type(torch.LongTensor)
data_test = torch.from_numpy(data_test).type(torch.LongTensor)
label_1_train = torch.from_numpy(label_1_train).type(torch.LongTensor)
label_2_train = torch.from_numpy(label_2_train).type(torch.LongTensor)
label_1_test = torch.from_numpy(label_1_test).type(torch.LongTensor)
label_2_test = torch.from_numpy(label_2_test).type(torch.LongTensor)


data_train = data_train.view(-1, 1,8,8).float()
data_test = data_test.view(-1, 1,8,8).float()


train = torch.utils.data.TensorDataset(data_train, label_1_train, label_2_train)
test = torch.utils.data.TensorDataset(data_test, label_1_test, label_2_test)

BATCH_SIZE = 64

train_loader = torch.utils.data.DataLoader(train, batch_size = BATCH_SIZE, shuffle = False)
test_loader = torch.utils.data.DataLoader(test, batch_size = BATCH_SIZE, shuffle = False)

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using {device} device")

class Model(nn.Module):
    def __init__(self):
        super(Model, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=2)
        self.conv2 = nn.Conv2d(32, 32, kernel_size=2)
        self.conv3 = nn.Conv2d(32,64, kernel_size=2)
        self.fc1 = nn.Linear(1*8*8, 256)
        self.fc2 = nn.Linear(256, 12)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        #x = F.dropout(x, p=0.5, training=self.training)
        x = F.relu(F.max_pool2d(self.conv2(x), 2))
        x = F.dropout(x, p=0.5, training=self.training)
        x = F.relu(F.max_pool2d(self.conv3(x),2))
        x = F.dropout(x, p=0.5, training=self.training)
        x = x.view(-1,1*8*8 )
        x = F.relu(self.fc1(x))
        x = F.dropout(x, training=self.training)
        x = self.fc2(x)
        return F.log_softmax(x, dim=1)


# Instantiate a neural network model 
cnn = Model().to(device)
 
print(cnn)

it = iter(train_loader)
X_batch, Y1_batch, Y2_batch = next(it)

def fit(model, train_loader):
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    error = nn.CrossEntropyLoss()
    dataset_size = len(train_loader.dataset)
    EPOCHS = 10
    model.train()
    loss1_epoch = []
    loss2_epoch = []
    total_loss_epoch = []

    loss1_batch = []
    loss2_batch = []
    total_loss_batch = []
    for epoch in range(EPOCHS):
        correct = 0
        correct1 = 0
        correct2 = 0
        for batch_idx, (X_batch, Y1_batch, Y2_batch) in enumerate(train_loader):
            var_X_batch = X_batch.to(device)
            var_Y1_batch = Y1_batch.to(device)
            var_Y2_batch = Y2_batch.to(device)

            optimizer.zero_grad()

            output = model(var_X_batch)

            output = torch.split(output, [4,8], dim=1)
            #output = output.split(4,dim=1)


            loss = error(output[0], var_Y1_batch) + error(output[1], var_Y2_batch)
            
            output1 = torch.max(output[0], 1)[1]
            output2 = torch.max(output[1], 1)[1]
            loss.backward()
            optimizer.step()

            # Total correct predictions
            # predicted = torch.max(output.data, 1)[1] 
            correct1 += (output1 == var_Y1_batch).sum()
            correct2 += (output2 == var_Y2_batch).sum()
            correct = correct + (output1 == var_Y1_batch).sum() + (output2 == var_Y2_batch).sum()
            #print(correct)
            if batch_idx % 50 == 0:
                loss1_batch.append(error(output[0], var_Y1_batch))
                loss2_batch.append(error(output[1], var_Y2_batch))
                total_loss_batch.append( error(output[0], var_Y1_batch) + error(output[1], var_Y2_batch))   
                print('Epoch : {} [{}/{} ({:.0f}%)]\tLoss: {:.6f}\t Label1 Accuracy:{:.3f}%\t Label2 Accuracy:{:.3f}%\tAccuracy:{:.3f}%'.format(
                    epoch, batch_idx*BATCH_SIZE, dataset_size, 100.*batch_idx / len(train_loader),
                    loss.item(), float(correct1*100) / float(BATCH_SIZE*(batch_idx+1)), float(correct2*100) / float(BATCH_SIZE*(batch_idx+1)), float(correct*100) / float(2*BATCH_SIZE*(batch_idx+1))))
        loss1_epoch.append(error(output[0], var_Y1_batch))
        loss2_epoch.append(error(output[1], var_Y2_batch))
        total_loss_epoch.append( error(output[0], var_Y1_batch) + error(output[1], var_Y2_batch))     
                

    plt.plot(loss1_epoch, label = "4 Type")
    plt.plot(loss2_epoch, label = "8 Application")
    plt.plot(total_loss_epoch, label = "Total")
    plt.ylabel('Loss')
    plt.xlabel('Epoch')
    plt.title('CNN Network Loss_Epoch')
    plt.show()

    plt.plot(loss1_batch, label = "4 Type")
    plt.plot(loss2_batch, label = "8 Application")
    plt.plot(total_loss_batch, label = "Total")
    plt.ylabel('Loss')
    plt.xlabel('Batch')
    plt.title('CNN Network Loss_Batch')
    plt.show()

fit(cnn, train_loader)

def test_model(model):
    model.eval()
    correct = 0
    correct1 = 0
    correct2 = 0
    for batch_idx, (test_x, test_L1, test_L2) in enumerate(test_loader):
        test_L1 = test_L1.to(device)
        test_L2 = test_L2.to(device)
        test_x = test_x.to(device)

        output = model(test_x)
        output = torch.split(output, [4,8], dim=1)

        output1 = torch.max(output[0], 1)[1]
        output2 = torch.max(output[1], 1)[1]

        correct1 += (output1 == test_L1).sum()
        correct2 += (output2 == test_L2).sum()
        correct = correct + ( (output1 == test_L1).sum() + (output2 == test_L2).sum() )
        
    print('Label1 Accuracy:{:.3f}%\t Label2 Accuracy:{:.3f}%\tAccuracy:{:.3f}%'.format(float(correct1*100) / float(BATCH_SIZE*(batch_idx+1)), float(correct2*100) / float(BATCH_SIZE*(batch_idx+1)), float(correct*100) / float(2*BATCH_SIZE*(batch_idx+1))))

test_model(cnn)
