# Evaluation results (2026-11-13 12:04)

## Ranking on 100 random futures (historical demand level, seed never used for building)
```
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 4,084,408 4,177     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 4,077,025 4,244     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 4,026,317 4,083     65      190          665         78,687
             stoch_joint   True    4,035,587 3,989,811 3,922     11      231          982        155,666
        stoch_joint_long   True    4,008,769 3,966,078 3,756     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 3,947,852 3,790     66      176          581         76,681
            stoch_pooled   True    3,932,479 3,881,842 3,619    105      222          338         34,258
                 det_raw   True    3,925,069 3,864,902 3,610    105      222          371         38,604
              det_pooled   True    3,918,518 3,860,454 3,634    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,837,421 3,540    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,822,484 3,491     91      233          345         35,856
                baseline   True    3,173,937 3,140,007 3,297     96        0            0              0
              do-nothing   True    3,057,212 3,025,408 3,094      0        0            0              0
Best: stoch_make_plan  (mean 4,084,408 +- 4,177) -> solution/best_plan.csv
Total 0s. Nothing was submitted.
```

## Stress test: seven ways of generating the hidden scenarios
```
== world: poisson_only
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 4,096,371 3,678     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 4,089,180 3,670     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 4,037,925 3,579     65      190          665         78,687
             stoch_joint   True    4,035,587 4,001,819 3,531     11      231          982        155,666
        stoch_joint_long   True    4,008,769 3,975,163 3,459     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 3,958,709 3,423     66      176          581         76,681
            stoch_pooled   True    3,932,479 3,891,624 3,229    105      222          338         34,258
                 det_raw   True    3,925,069 3,874,864 3,171    105      222          371         38,604
              det_pooled   True    3,918,518 3,870,139 3,143    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,846,596 3,071    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,831,427 2,983     91      233          345         35,856
                baseline   True    3,173,937 3,148,176 2,740     96        0            0              0
              do-nothing   True    3,057,212 3,034,473 2,593      0        0            0              0
== world: shared_shift
                    plan  valid  on_forecast      mean     se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 4,083,931 28,100     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 4,075,961 28,265     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 4,024,925 27,314     65      190          665         78,687
             stoch_joint   True    4,035,587 3,987,247 25,000     11      231          982        155,666
        stoch_joint_long   True    4,008,769 3,964,424 24,669     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 3,945,194 24,979     66      176          581         76,681
            stoch_pooled   True    3,932,479 3,879,204 22,379    105      222          338         34,258
                 det_raw   True    3,925,069 3,860,975 22,195    105      222          371         38,604
              det_pooled   True    3,918,518 3,857,752 22,092    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,835,238 20,997    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,820,960 20,410     91      233          345         35,856
                baseline   True    3,173,937 3,139,709 16,636     96        0            0              0
              do-nothing   True    3,057,212 3,026,918 14,462      0        0            0              0
== world: demand_-15%
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 3,598,945 4,104     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 3,589,666 4,203     48      187          676         82,475
             stoch_joint   True    4,035,587 3,552,704 4,013     11      231          982        155,666
       stoch_joint_up0.5   True    4,073,682 3,551,690 4,145     65      190          665         78,687
        stoch_joint_long   True    4,008,769 3,536,009 3,915     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 3,506,742 4,027     66      176          581         76,681
            stoch_pooled   True    3,932,479 3,487,280 3,777    105      222          338         34,258
                 det_raw   True    3,925,069 3,469,949 3,749    105      222          371         38,604
              det_pooled   True    3,918,518 3,468,891 3,679    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,465,298 3,558    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,461,547 3,467     91      233          345         35,856
                baseline   True    3,173,937 2,849,373 3,099     96        0            0              0
              do-nothing   True    3,057,212 2,774,818 2,837      0        0            0              0
== world: demand_+15%
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 4,488,796 4,186     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 4,486,008 4,212     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 4,416,725 4,073     65      190          665         78,687
             stoch_joint   True    4,035,587 4,341,566 3,847     11      231          982        155,666
        stoch_joint_long   True    4,008,769 4,317,309 3,927     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 4,299,297 3,760     66      176          581         76,681
            stoch_pooled   True    3,932,479 4,196,764 3,656    105      222          338         34,258
                 det_raw   True    3,925,069 4,171,419 3,513    105      222          371         38,604
              det_pooled   True    3,918,518 4,169,067 3,582    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 4,131,055 3,550    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 4,108,389 3,541     91      233          345         35,856
                baseline   True    3,173,937 3,385,696 3,377     96        0            0              0
              do-nothing   True    3,057,212 3,241,706 3,148      0        0            0              0
== world: booking_level
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 4,230,123 4,112     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 4,224,612 4,288     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 4,156,709 4,099     65      190          665         78,687
             stoch_joint   True    4,035,587 4,093,485 4,028     11      231          982        155,666
       stoch_joint_up0.0   True    3,999,128 4,078,922 3,907     66      176          581         76,681
        stoch_joint_long   True    4,008,769 4,067,216 3,771     20      233          884        140,696
            stoch_pooled   True    3,932,479 4,014,254 3,440    105      222          338         34,258
                 det_raw   True    3,925,069 3,991,850 3,349    105      222          371         38,604
              det_pooled   True    3,918,518 3,991,738 3,356    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,964,204 3,196    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,944,446 3,107     91      233          345         35,856
                baseline   True    3,173,937 3,306,988 3,149     96        0            0              0
              do-nothing   True    3,057,212 3,193,248 2,907      0        0            0              0
== world: rental_sim
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 3,929,387 6,217     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 3,919,384 6,172     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 3,872,991 6,169     65      190          665         78,687
             stoch_joint   True    4,035,587 3,840,038 5,934     11      231          982        155,666
        stoch_joint_long   True    4,008,769 3,825,333 5,961     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 3,791,614 5,748     66      176          581         76,681
            stoch_pooled   True    3,932,479 3,722,622 5,199    105      222          338         34,258
                 det_raw   True    3,925,069 3,711,837 5,198    105      222          371         38,604
              det_pooled   True    3,918,518 3,701,482 5,083    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,685,909 4,852    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,675,128 4,719     91      233          345         35,856
                baseline   True    3,173,937 3,009,918 4,395     96        0            0              0
              do-nothing   True    3,057,212 2,914,584 4,228      0        0            0              0
== world: rental_sim_booking
                    plan  valid  on_forecast      mean    se  added  removed  transferred  transfer_cost
         stoch_make_plan   True    4,128,191 4,028,270 5,964     48      200          674         84,512
stoch_joint_upcell_blend   True    4,118,622 4,020,229 6,015     48      187          676         82,475
       stoch_joint_up0.5   True    4,073,682 3,962,955 5,802     65      190          665         78,687
             stoch_joint   True    4,035,587 3,912,768 5,399     11      231          982        155,666
        stoch_joint_long   True    4,008,769 3,896,212 5,444     20      233          884        140,696
       stoch_joint_up0.0   True    3,999,128 3,881,195 5,413     66      176          581         76,681
            stoch_pooled   True    3,932,479 3,813,794 4,960    105      222          338         34,258
                 det_raw   True    3,925,069 3,802,392 4,995    105      222          371         38,604
              det_pooled   True    3,918,518 3,792,293 4,854    104      220          359         36,866
         det_pooled_x0.9   True    3,887,236 3,773,707 4,682    100      224          336         34,682
         det_pooled_x0.8   True    3,869,332 3,760,540 4,614     91      233          345         35,856
                baseline   True    3,173,937 3,118,722 4,537     96        0            0              0
              do-nothing   True    3,057,212 3,023,162 4,195      0        0            0              0
First place (plans within 2 SE of the top) per world:
  poisson_only   ['stoch_make_plan', 'stoch_joint_upcell_blend']
  shared_shift   ['stoch_make_plan', 'stoch_joint_upcell_blend']
  demand_-15%    ['stoch_make_plan']
  demand_+15%    ['stoch_make_plan', 'stoch_joint_upcell_blend']
  booking_level  ['stoch_make_plan', 'stoch_joint_upcell_blend']
  rental_sim     ['stoch_make_plan', 'stoch_joint_upcell_blend']
  rental_sim_booking ['stoch_make_plan', 'stoch_joint_upcell_blend']
```
