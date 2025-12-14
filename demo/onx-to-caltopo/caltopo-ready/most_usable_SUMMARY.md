## Cairn shape dedup summary

This file explains why some shapes were removed from the primary CalTopo import file.
Nothing is deleted permanently: every dropped feature is preserved in the secondary GeoJSON.

### Inputs
- **GPX**: `demo/onx-to-caltopo/onx-export/onx-export.gpx`
- **KML**: `demo/onx-to-caltopo/onx-export/onx-export.kml`

### Outputs
- **Primary (deduped)**: `/Users/scott/_code/carin/demo/onx-to-caltopo/caltopo-ready/most_usable.json`
- **Secondary (dropped duplicates)**: `/Users/scott/_code/carin/demo/onx-to-caltopo/caltopo-ready/most_usable_dropped_shapes.json`

### Dedup policy
- **Polygon preference**: when the same onX id exists as both a route/track (GPX) and a polygon (KML), we keep the polygon and drop the line to avoid CalTopo id collisions.
- **Shape dedup default**: enabled (can be disabled via `--no-dedupe-shapes`).
- **Fuzzy match definition**:
  - **Polygons**: round coordinates to 6 decimals; ignore ring start index; ignore ring direction.
  - **Lines**: round coordinates to 6 decimals; treat reversed line as equivalent.

### Dedup results
- **Waypoint dedup dropped**: 94
- **Shape dedup groups**: 21
- **Shape dedup dropped features**: 81

### Per-group decisions

- **Polygon** `Carlton lake potential zone`
  - **kept**: `556c1911-845a-423a-b39a-4a28403ce941`
  - **dropped (7)**: `3d7adbf1-4258-4e69-bc21-eb83ec095b68`, `29b5a7db-d38a-495b-b4a3-6c063f36b50e`, `7763e8a0-bdaf-4213-bc63-32854e856562`, `d15011e7-ea61-40ad-a409-834b1e691d22`, `b5825c4a-83f6-415d-8763-5d6711bf0a6f`, `67e64e87-748a-4b76-9de7-1bb17dce3918`, `b144c82c-b056-43e1-82aa-37f40d66014d`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `McCalla lake bowl`
  - **kept**: `d536aa0d-ff75-4adf-9a0e-0830900d2b03`
  - **dropped (7)**: `9d66fc98-e303-44de-8d05-92de742eb5da`, `3e50d4ba-b084-448b-b301-84f0144a2f05`, `46466caf-26b0-42b3-b4b2-7d745aca48ce`, `52444f24-dba7-4745-8f55-b198b7e71d9f`, `1bff96fe-b818-47f0-9ab8-91123d924e03`, `644ec4fd-21d1-42ef-abc2-dd7c28ef8cd1`, `c9897d8f-2dce-4f68-9fc7-367bacddb331`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `St Mary south trees`
  - **kept**: `1f52574e-96d1-4dc4-a7b5-13227e7afd60`
  - **dropped (7)**: `1a2b21fb-fdb8-4377-a1ed-b69395e0b470`, `c9bcf773-ca7b-410c-9813-fb47adcad693`, `b0cb8126-2278-48fa-991f-856771e5cefc`, `6c825dc6-858f-446c-b43c-929335797de6`, `5f742faf-663d-4a47-af4c-af47c62072f8`, `427083ad-a91c-4795-9bef-aa2dabb7be73`, `64a383b2-70cb-4469-9087-c289ba56359b`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `St Mary E bowl`
  - **kept**: `74dd5849-3dc4-4bdc-934b-709105ce4279`
  - **dropped (7)**: `ae7d660e-7102-49dd-819b-6ed05541a1e6`, `ac77972c-19d7-4482-a31c-756cc969ad96`, `33bd5832-19ef-49d3-8f2f-07bf01404185`, `c7de63f1-faee-4385-ab2a-81a0ee2d0c67`, `896ff84a-a8a6-42b5-9ff4-794a58e962fe`, `417ed44d-4467-4e7f-a0df-3fb3b285dff3`, `a2f2ce6c-435c-4af1-aec7-2f53ad20828b`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `S Bowl`
  - **kept**: `90bccd0a-e585-4095-bff2-12d32f2f14d0`
  - **dropped (7)**: `50cd0f70-73d7-412b-a4fb-049202a962c5`, `3c914923-737f-4249-9e92-d36e4900f173`, `8f8b86ff-efe9-45e1-916c-b96f3609fce0`, `13c4bf00-0441-4085-9066-b745c5d71f6b`, `94df4394-2619-488a-b5fb-d9f8cd51b34f`, `595d5adf-eafc-4796-adfe-3236363d9237`, `bbdc18ec-ca8a-4be4-9bb6-81a1c055ab1e`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `N Bowl`
  - **kept**: `1b5e6913-153d-4be5-a663-e258b9ed131d`
  - **dropped (7)**: `938654d1-ddeb-44c7-b40a-0a2ec3adc703`, `faac0872-846e-40b5-ace7-7f652eefd773`, `f8cbd688-c038-422e-a8b6-c9345ec01abe`, `35fde15d-28fa-43c9-ae13-af39175ff1e1`, `4959b0a2-5345-4764-a14c-562af94b6690`, `b5ab47d9-06c8-4e6c-9141-895d4e107c3a`, `07d3baeb-d81b-49cd-a147-ff55a8289605`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `Burn glade skiing`
  - **kept**: `2769dec9-cf89-4a1a-b9f0-9d6a0303d8c6`
  - **dropped (7)**: `d91951fa-9e76-42e3-af92-702ed61a813e`, `bf0e7c86-e306-4bb4-8850-9ee0999941ea`, `8b2e73e1-cf96-405e-a3ff-aa1eb15d69b5`, `f57cbc39-4bd0-4952-a190-7b7e10622da7`, `7eac98a5-d7e4-45ef-b388-71e9b7a5e89c`, `5bf801c9-5cdb-47dc-a1d3-7fe18eb3a719`, `f9bd928e-8a7e-4edb-b710-1c14b4b47aa8`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `Gash main bowl`
  - **kept**: `72c84ceb-92c2-4490-ba54-1e7a1e0fdeb0`
  - **dropped (7)**: `4a7bde7a-074b-481e-9c68-d92836900166`, `7f2022ae-eb57-4d30-9bc0-ced0b44c03c1`, `bbf6480a-17dd-4518-8a31-3cd8953d3640`, `2ae0dccd-8629-49cc-b188-bc243944e652`, `64f00fd9-5bf6-40a0-8096-d8ae2806d0ab`, `7fdf6801-b645-45ed-95bb-5387b204878e`, `09e71b16-97ab-4c2b-b83a-8883d3fe17dc`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `very cool alpine-y terrain`
  - **kept**: `e33f02db-12e9-42b3-8ac7-1d8847331720`
  - **dropped (7)**: `5da361b4-c53a-4b15-95b4-c62e8b5d8d04`, `d255944b-7a90-4fef-b0ce-8630091c6629`, `49192282-b809-46cb-9d0c-3d83f79ffcc9`, `eb5ef944-102f-4869-9c44-cfcad1da7619`, `c01947c0-a2ba-40fe-928b-bc7cd308a96f`, `1c3d378f-9d8f-48ad-a1e1-dc9a89d13420`, `145cd6a7-d8a3-45c8-88e4-a8b9a69c1dfc`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `Sweeney east glade`
  - **kept**: `0e936f26-0fe2-4202-8aa3-843ba4dcc0d2`
  - **dropped (7)**: `4e213509-db23-4780-bebf-9e6fb5c23fed`, `c6642f5c-8d4c-4351-9a8d-919050b0d48a`, `ae81a812-9535-409b-a153-2a5fb4751484`, `ec0f1dad-0733-4ec0-bacb-000896cd5d98`, `c1e3f6bb-f122-4618-80b5-dfcd5d96809c`, `ebae3950-33be-4dde-8465-75c548959d2b`, `cbc9ed3c-9df6-4e29-a4e6-b4fbbc83c16b`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-Carlton lake potential zone`
  - **kept**: `c92e7ff8-2803-4350-9199-db7824228205`
  - **dropped (1)**: `549a327c-2104-4199-b9bf-7d20bedde1b0`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-McCalla lake bowl`
  - **kept**: `fefdd5f7-2040-4001-b718-ce309d03627a`
  - **dropped (1)**: `e80c6e66-b1c3-49d3-bff8-f6b036e698ec`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-St Mary south trees`
  - **kept**: `a7c1c6d3-bbaa-439e-af1d-9d6241eef715`
  - **dropped (1)**: `7a8051aa-e8f2-4869-bd6e-6bd047700f13`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-St Mary E bowl`
  - **kept**: `21d9723c-506c-4d93-aed7-426527d0a5eb`
  - **dropped (1)**: `b6600dfe-3496-4cd5-a076-5546b08f9a35`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-S Bowl`
  - **kept**: `f4587ff8-fbce-4866-ae0b-4266de743d62`
  - **dropped (1)**: `6bdbbc51-6d0d-45ee-823b-1826d56b997b`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-N Bowl`
  - **kept**: `a398f822-ce62-49be-ae03-0539c4933991`
  - **dropped (1)**: `383297a5-ad35-4d27-ac8a-fe860b05970b`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-Burn glade skiing`
  - **kept**: `2f127d2a-a7d4-49e3-9cfc-78f07be002c7`
  - **dropped (1)**: `96a546d4-3534-4977-9aa8-a223b96c5574`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-Gash main bowl`
  - **kept**: `d60808b7-4557-47b4-a32d-0db46f31909f`
  - **dropped (1)**: `d36cae68-99e0-4b7b-b15e-128e29266b2d`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-very cool alpine-y terrain`
  - **kept**: `c8793839-542a-4169-87cb-2512e42ce351`
  - **dropped (1)**: `c3d81b16-6379-4879-ab09-099c21a11fae`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-`
  - **kept**: `4fe03983-ab20-4b32-a299-f70a824e9b65`
  - **dropped (1)**: `2dc22836-a9c5-47d8-8b3c-339498086d39`
  - **reason**: fuzzy_geometry_signature_match
- **Polygon** `cairn-Sweeney east glade`
  - **kept**: `76d3872b-464d-496d-9e93-13669b4137ac`
  - **dropped (1)**: `744ce6f6-6c7d-4248-be3b-2f08a7dadfc1`
  - **reason**: fuzzy_geometry_signature_match
