# LR-JSONParser

This repository is intended to help integrate different APIs into LogRhythm, although it may be useful in other scenarios.

Use the [TOML](https://toml.io/en/) language the config, this is a config file format for humans.


```mermaid
graph LR

%% Entity A con múltiples sources y endpoints
A[Entity A] --> B1[Source / Technology A.1] --> E1[Endpoint A.1.1]
B1 --> E2[Endpoint A.1.2]
A --> C1[Source / Technology A.2] --> E3[Endpoint A.2.1]
C1 --> E4[Endpoint A.2.2]

%% Entity B con múltiples sources y endpoints
D[Entity B] --> B2[Source / Technology B.1] --> E5[Endpoint B.1.1]
B2 --> E6[Endpoint B.1.2]
D --> C2[Source / Technology B.2] --> E7[Endpoint B.2.1]
C2 --> E8[Endpoint B.2.2]
```
