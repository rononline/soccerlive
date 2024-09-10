# Calcio Live - Home Assistant Integration

## Descrizione
L'integrazione "Calcio Live" per Home Assistant permette di ottenere informazioni in tempo reale sulle competizioni di calcio, come classifiche, cannonieri e giornate di campionato.

## Installazione tramite HACS
1. Aggiungi il repository `https://github.com/tuo_username/calcio_live` in HACS.
    ![INSTALLAZIONE](images/installazione-git.png)
    
2. Cerca "Calcio Live" in HACS e installa l'integrazione.
    ![HACS](images/hacs.png)

3. Devi avere un codice API e per ottenerlo vai su: https://www.football-data.org/client/register
   registrati e ottieni la tua chiave API che arriva sull'e-mail-

3. Vai su Impostazioni > Integrazione > Aggiungi Integrazione e cerca 'Calcio-Live' 

4. Configura l'integrazione tramite l'interfaccia di Home Assistant.

5. Inserisci API Key nella prima riga
   Scegli il campionato da seguire
   Scegli nome che avra il sensore (se scrivi serie a, il sensore sarà sensor.calciolive_seriea_xxx)
   
    ![HACS](images/integrazione1.png)
    ![HACS](images/integrazione2.png)
   
6. Per la card, vai su: https://github.com/Bobsilvio/calcio-live-card e segui le istruzioni

Note: Puoi usare la stessa api key per piu campionati, ricordati di dare un nome al campionato

## Utilizzo dei sensori
Vengono creati 4 sensori:

- sensor.calciolive_nomescelto_competizioni
  Questo sensore viene creato per ogni campionato, ma è uguale a tutti, è la lista dei campionati e delle giornate in corso

- sensor.calciolive_nomescelto_cannonieri
  Ci da la classifica dei capocannonieri del campionato

- sensor.sensor.calciolive_nomescelto_classifica
  Ci da la classifica del campionato

- sensor.calciolive_nomescelto_match_day
  Ci da le sfide della giornata in corso o future (nel caso siano finite tutte le partite)

## Informazioni
Questa è la mia prima card e sicuramente c'è tanto lavoro da fare, se vi piace, potete ricambiare seguendomi nei social:

TikTok: @silviosmartalexa