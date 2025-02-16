## Assemble BeefLettuceBurger



### Comb1[[Beef, Lettuce, Bread]]
Comb1[[Beef, Lettuce, Bread]] only need to process a BeefLettuce.
```mermaid
flowchart TD
Begin[BeefLettuceBurger] --> Comb1[[Beef, Lettuce, Bread]] & Comb2[[LettuceBurger, Beef]] & Comb3[[BeefLettuce, Bread]] & Comb4[[BeefBurger, Lettuce]]

Comb1 --> Cond0([lettuce_in_plate is closer to the ready pan?])
Cond0 --> |Yes| Pick1([pickup_lettuce_in_plate]) --> Plate1([plate_beef_done_from_pan]) & Plate2([plate_beef_done])
Cond0 --> |No| Cond1{Beef on Pan?}
Cond1 --> |Yes| Get1([get_plate]) --> Plate5([plate_beef_done_from_pan]) --> Plate4([plate_lettuce_done])
Cond1 --> |No| Pick2([pickup_beef_done]) --> Plate4
```


### Comb2[[LettuceBurger, Beef]]

```mermaid
flowchart TD
Begin[BeefLettuceBurger] --> Comb1[[Beef, Lettuce, Bread]] & Comb2[[LettuceBurger, Beef]] & Comb3[[BeefLettuce, Bread]] & Comb4[[BeefBurger, Lettuce]]

Comb2 --> Cond0([beeflettuce is closer to the ready pan?])
Cond0 --> |Yes| Pick1(pickup_lettuceburger) --> Plate1([plate_beef_done_from_pan]) & Plate2([plate_beef_done])
Cond0 --> |No| Get1([get_plate]) --> Plate4([plate_beef_done_from_pan]) & Plate5([plate_beef_done]) --> Plate3([plate_lettuceburger])
```


### Comb3[[BeefLettuce, Bread]]

```mermaid
flowchart TD
Begin[BeefLettuceBurger] --> Comb1[[Beef, Lettuce, Bread]] & Comb2[[LettuceBurger, Beef]] & Comb3[[BeefLettuce, Bread]] & Comb4[[BeefBurger, Lettuce]]

Comb3 --> Cond1{Bread on Counter?}
Cond1 --> |No| Get1([get_bread]) --> Put1([put_onto_beeflettuce]) & Plate1([plate_beeflettuce])
Cond1 --> |Yes| Pick1([pickup_beeflettuce]) --> Plate2([plate_bread])
```

### Comb4[[BeefBurger, Lettuce]]

```mermaid
flowchart TD
Begin[BeefLettuceBurger] --> Comb1[[Beef, Lettuce, Bread]] & Comb2[[LettuceBurger, Beef]] & Comb3[[BeefLettuce, Bread]] & Comb4[[BeefBurger, Lettuce]]

Comb4 --> Pick1([pickup_beefburger]) --> Plate1([plate_lettuce_done])

```
