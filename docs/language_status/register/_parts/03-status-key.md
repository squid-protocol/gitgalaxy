## Status key

| status | meaning |
|---|---|
| **MATCHED** | The oracle is made to behave as IBM documents it (a flag, a model or a shim), and a test pins it. |
| **REFUSED** | IBM's behaviour is not settled by its documentation, so the harness stops by name ("not modelled") and no proof rests on a guess. |
| **DIFFERS** | A known difference between the oracle and z/OS. The entry says whether any proven program reaches it. |
| **ASSUMED** | Believed to match, and not measured on z/OS. |

"Reached" means a proven program's scenarios execute the behaviour. An unreached difference cannot have changed a
verdict, but it limits what the proof says about inputs outside the scenarios.
