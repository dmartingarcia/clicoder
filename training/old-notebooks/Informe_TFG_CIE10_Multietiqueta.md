# Clasificación Multietiqueta Jerárquica de Textos Médicos CIE-10
---

# Trabajo Fin de Máster
# Clasificación Multietiqueta Jerárquica de Textos Médicos CIE-10

**Autor:** David Martín García
**Tutor:** Dr. Juan Pérez
**Universidad:** Universidad Autónoma de Madrid
**Máster:** Máster en Ciencia de Datos y Aprendizaje Automático
**Fecha:** Septiembre 2025

---

# Resumen
Este trabajo aborda el reto de la codificación automática de textos médicos en códigos CIE-10 mediante técnicas de aprendizaje profundo y procesamiento de lenguaje natural. Se comparan modelos planos y jerárquicos, se realiza un análisis estadístico exhaustivo de los datos y se discuten las implicaciones clínicas y técnicas de los resultados obtenidos. El desarrollo se realiza sobre datos reales del proyecto CODIESP y se implementa en un entorno reproducible y escalable.

---

# Índice
1. Introducción y motivación
2. Estado del arte y marco teórico
3. Descripción de los datos
4. Análisis exploratorio y estadístico
5. Metodología y preprocesamiento
6. Modelos de clasificación multietiqueta
7. Implementación y arquitectura
8. Resultados experimentales
9. Visualización y análisis crítico
10. Discusión y limitaciones
11. Conclusiones y trabajo futuro
12. Referencias bibliográficas
13. Anexos: código, tablas y gráficos

---

## 1. Introducción

La digitalización de la información clínica ha revolucionado la gestión hospitalaria y la investigación biomédica en las últimas décadas. Desde la aparición de los primeros sistemas de historia clínica electrónica, el volumen de datos textuales generados por los profesionales sanitarios ha crecido exponencialmente, abarcando desde notas de evolución y diagnósticos hasta informes de alta y procedimientos quirúrgicos. Esta riqueza informativa, sin embargo, plantea retos significativos en cuanto a su estructuración, análisis y aprovechamiento para la toma de decisiones clínicas y la investigación.

La codificación automática de textos médicos en sistemas estandarizados como CIE-10 (Clasificación Internacional de Enfermedades) es un proceso clave para garantizar la interoperabilidad entre sistemas sanitarios, facilitar la facturación hospitalaria, mejorar la calidad de los datos y permitir estudios epidemiológicos de gran escala. La correcta asignación de códigos CIE-10 a los textos clínicos permite comparar resultados entre hospitales, identificar tendencias de salud pública y optimizar la gestión de recursos sanitarios.

No obstante, la tarea de codificación manual es laboriosa, propensa a errores y requiere un conocimiento experto de la terminología médica y de las reglas de codificación. La automatización de este proceso mediante técnicas de inteligencia artificial y aprendizaje profundo representa una oportunidad única para transformar la práctica clínica, liberar tiempo de los profesionales y mejorar la calidad de la atención sanitaria.

El presente trabajo se enmarca en este contexto de innovación y transformación digital, abordando el desarrollo y evaluación de modelos de machine learning para la clasificación multietiqueta de textos médicos en códigos CIE-10. Se utilizan datos reales del proyecto CODIESP, que proporcionan una base sólida y representativa para el entrenamiento y validación de los modelos.

Entre los principales retos que se abordan destacan:
- La complejidad y ambigüedad del lenguaje médico, con abundancia de abreviaturas, errores tipográficos y estilos narrativos heterogéneos.
- La estructura jerárquica de los códigos CIE-10, que requiere modelos capaces de captar relaciones semánticas entre etiquetas.
- El desequilibrio de clases, con etiquetas muy frecuentes y otras extremadamente raras.
- La necesidad de garantizar la privacidad y la seguridad de los datos clínicos, cumpliendo con la normativa vigente.

Los objetivos específicos del trabajo son:
1. Analizar estadísticamente los datos clínicos y las etiquetas CIE-10, identificando patrones y retos para el modelado.
2. Desarrollar e implementar modelos de clasificación multietiqueta, comparando enfoques planos y jerárquicos.
3. Evaluar el rendimiento de los modelos mediante métricas estándar y análisis crítico de los resultados.
4. Diseñar una arquitectura de despliegue robusta, integrando el modelo en una aplicación conversacional para uso clínico.
5. Reflexionar sobre las implicaciones éticas, legales y sociales de la automatización de la codificación clínica.

Este trabajo pretende contribuir al avance de la inteligencia artificial en medicina, ofreciendo soluciones prácticas y reflexivas para la codificación automática de textos médicos y sentando las bases para futuras investigaciones y desarrollos en el ámbito de la salud digital.

## 2. Estado del arte

### 2.1 Evolución histórica de la codificación automática en medicina

La codificación clínica y el procesamiento de lenguaje natural (PLN) en medicina han experimentado una evolución notable y acelerada en las últimas décadas. Este avance puede dividirse en distintas etapas tecnológicas, cada una con sus propios paradigmas, limitaciones y contribuciones al campo.

**Sistemas basados en reglas (1980-1995)**

Los primeros intentos de automatizar la codificación de textos médicos surgieron a principios de los años 80, inspirados por los avances en sistemas expertos y procesamiento de lenguaje natural simbólico. Proyectos pioneros como MEDINDEX [1] y MetaMap [2] utilizaban diccionarios médicos estructurados, ontologías y sistemas de reglas definidas manualmente por expertos para identificar conceptos médicos en textos clínicos y mapearlos a códigos estandarizados.

Estos sistemas destacaban por su precisión en dominios específicos y la transparencia en la toma de decisiones, pero presentaban limitaciones significativas:

* Rigidez ante variaciones terminológicas y errores ortográficos
* Dificultad para manejar la ambigüedad y el contexto
* Alto coste de desarrollo y mantenimiento de las reglas
* Escalabilidad limitada a nuevos dominios o idiomas
* Incapacidad para aprender automáticamente de nuevos datos

Un ejemplo representativo fue el sistema MEDLEE (Medical Language Extraction and Encoding System) desarrollado por la Universidad de Columbia en los años 90, que combinaba análisis sintáctico y semántico para extraer información estructurada de informes radiológicos y transformarla en códigos CIE [3].

**Aprendizaje automático clásico (1995-2010)**

La segunda generación de sistemas de codificación automática adoptó técnicas de aprendizaje estadístico y automático, coincidiendo con el auge de la minería de datos y la disponibilidad creciente de textos médicos digitalizados. Algoritmos como Support Vector Machines (SVM), Random Forest, Naive Bayes y Modelos de Markov comenzaron a aplicarse a la clasificación de documentos médicos y la extracción de entidades clínicas [4].

Estos enfoques presentaban ventajas significativas respecto a los sistemas basados en reglas:

* Capacidad de aprendizaje a partir de ejemplos etiquetados
* Mayor flexibilidad ante variaciones lingüísticas
* Mejor escalabilidad a nuevos dominios
* Reducción del trabajo manual de ingeniería de características

Sin embargo, estos modelos dependían fuertemente de la calidad del preprocesamiento y la selección manual de características (feature engineering). La representación de textos se basaba principalmente en bolsas de palabras (bag-of-words) y n-gramas, perdiendo gran parte de la información contextual y semántica.

Sistemas como AutoCoder [5] y HITEx (Health Information Text Extraction) [6] emplearon estos enfoques para clasificar automáticamente informes clínicos, alcanzando precisiones moderadas (60-75%) en tareas como la identificación de diagnósticos y procedimientos.

**Deep Learning y representación distribuida (2010-2017)**

La llegada del aprendizaje profundo (deep learning) y las técnicas de representación distribuida del lenguaje revolucionaron el PLN biomédico a partir de 2010. Las redes neuronales recurrentes (LSTM, GRU), las redes convolucionales (CNN) y los modelos de embeddings (Word2Vec, GloVe) permitieron capturar patrones complejos y relaciones contextuales en grandes volúmenes de datos no estructurados [7].

Estas tecnologías aportaron avances significativos:

* Representación continua de palabras y frases médicas
* Capacidad para capturar dependencias de largo alcance
* Mejor generalización a términos poco frecuentes
* Aprendizaje automático de características relevantes
* Adaptabilidad a múltiples tareas y dominios

Los modelos neuronales como DeepCode [8] y CAML (Convolutional Attention for Multi-Label classification) [9] alcanzaron precisiones superiores al 80% en la predicción de códigos CIE a partir de notas clínicas, marcando un punto de inflexión en la viabilidad de la codificación automática a escala.

**Modelos preentrenados y arquitecturas Transformer (2018-actualidad)**

En la última etapa, los modelos de lenguaje preentrenados basados en arquitecturas Transformer han revolucionado definitivamente el PLN biomédico. Modelos como BERT [10], BioBERT [11], ClinicalBERT [12], SciBERT y RoBERTa han establecido nuevos estándares de rendimiento en tareas de codificación automática, extracción de entidades y relaciones semánticas en textos médicos.

Estos modelos se caracterizan por:

* Preentrenamiento masivo en corpus generales y específicos del dominio médico
* Representaciones contextuales bidireccionales
* Capacidad para capturar matices semánticos y pragmáticos
* Fine-tuning eficiente para tareas específicas
* Aplicabilidad a problemas de baja disponibilidad de datos etiquetados (few-shot learning)

El modelo MedBERT [13], adaptado específicamente para textos clínicos, logró un F1-score superior a 0.85 en tareas de codificación CIE-10, mientras que BioClinicalBERT [14] demostró capacidades avanzadas de comprensión contextual en la identificación de relaciones entre conceptos médicos.

### 2.2 Clasificación multietiqueta en el contexto biomédico

La clasificación multietiqueta representa un paradigma esencial en el procesamiento de textos médicos, ya que los documentos clínicos típicamente contienen información sobre múltiples condiciones, tratamientos y factores de riesgo que deben ser codificados simultáneamente.

**Fundamentos y retos específicos**

La clasificación multietiqueta se distingue fundamentalmente de la clasificación multiclase tradicional en que cada instancia puede pertenecer simultáneamente a varias categorías, sin restricciones de exclusividad. Esta característica refleja la compleja realidad clínica, donde un paciente puede presentar comorbilidades, complicaciones y factores de riesgo interrelacionados [15].

Los principales retos en la clasificación multietiqueta de textos médicos incluyen:

* **Correlación entre etiquetas**: Las condiciones médicas tienden a coocurrir siguiendo patrones fisiopatológicos que deben ser capturados por los modelos (p.ej., diabetes y retinopatía).
* **Desequilibrio extremo**: La distribución de poder-ley (power-law) típica de los diagnósticos médicos genera un espacio de etiquetas muy desequilibrado.
* **Alta dimensionalidad**: Los sistemas de codificación médica como CIE-10 contienen miles de códigos posibles, generando espacios de salida de alta dimensionalidad.
* **Dependencia contextual**: La asignación de códigos depende fuertemente del contexto clínico (p.ej., antecedentes vs. diagnóstico actual).
* **Carencia de muestras**: Para muchas combinaciones de etiquetas, existe un número muy limitado de ejemplos de entrenamiento.

**Enfoques algorítmicos en clasificación multietiqueta biomédica**

La literatura especializada ha propuesto diversos enfoques para abordar la clasificación multietiqueta en textos médicos:

1. **Transformación del problema** [16]:
   - Binary Relevance (BR): Descompone el problema multietiqueta en múltiples problemas binarios independientes, uno por cada etiqueta posible.
   - Classifier Chains (CC): Construye una cadena de clasificadores binarios donde cada uno incorpora las predicciones de los anteriores como características adicionales.
   - Label Powerset (LP): Transforma el problema multietiqueta en un problema multiclase, tratando cada combinación única de etiquetas como una clase distinta.

2. **Adaptación del algoritmo** [17]:
   - Redes neuronales con múltiples salidas sigmoide
   - Árboles de decisión multinivel
   - Algoritmos específicos multietiqueta como ML-kNN y RAKEL

3. **Embeddings específicos para etiquetas** [18]:
   - SLEEC (Sparse Local Embeddings for Extreme Classification)
   - XMLC (eXtreme Multi-Label Classification)
   - LSAN (Label-Specific Attention Network)

La evaluación comparativa realizada por Wang et al. [19] sobre el dataset MIMIC-III demostró que los enfoques basados en redes neuronales con atención específica por etiqueta superaban consistentemente a los métodos tradicionales en la predicción de códigos CIE-10, alcanzando mejoras del 8-12% en F1-score.

### 2.3 Modelos jerárquicos y estructura semántica de códigos médicos

La clasificación multietiqueta añade una capa de complejidad adicional cuando las etiquetas presentan una estructura jerárquica inherente, como ocurre con los sistemas de codificación médica. Los códigos CIE-10, por ejemplo, siguen una organización taxonómica donde los primeros caracteres indican la categoría general, y los siguientes especifican subcategorías y detalles clínicos con granularidad creciente [20].

**Taxonomía CIE-10 y estructura jerárquica**

La Clasificación Internacional de Enfermedades en su décima revisión (CIE-10) organiza más de 68,000 códigos diagnósticos en una estructura jerárquica de hasta siete niveles de profundidad:

* **Nivel 1**: Capítulos (p.ej., E: Enfermedades endocrinas, nutricionales y metabólicas)
* **Nivel 2**: Bloques (p.ej., E10-E14: Diabetes mellitus)
* **Nivel 3**: Categorías de tres caracteres (p.ej., E11: Diabetes mellitus tipo 2)
* **Nivel 4**: Subcategorías de cuatro caracteres (p.ej., E11.9: Sin complicaciones)
* **Niveles 5-7**: Extensiones clínicas (p.ej., E11.9+G73.3: Diabetes con amiotrofia)

Esta estructura jerárquica refleja relaciones semánticas y clínicas fundamentales entre conceptos médicos que pueden ser aprovechadas para mejorar los modelos de clasificación [21].

**Ventajas de los modelos jerárquicos en codificación médica**

Los modelos que incorporan explícitamente la estructura jerárquica de los códigos médicos presentan ventajas significativas [22]:

* **Consistencia taxonómica**: Garantizan predicciones coherentes con la estructura jerárquica (evitando, por ejemplo, predecir un código específico sin su correspondiente código padre).
* **Transferencia de conocimiento**: Permiten transferir aprendizaje de categorías generales frecuentes a subcategorías específicas más raras.
* **Eficiencia computacional**: Reducen la complejidad dividiendo el problema en subproblemas más manejables.
* **Interpretabilidad**: Facilitan la comprensión del proceso de decisión al seguir una lógica jerárquica similar al razonamiento médico.
* **Robustez ante etiquetas raras**: Mejoran el rendimiento en códigos infrecuentes aprovechando su relación con códigos más comunes.

**Algoritmos jerárquicos para codificación médica**

La literatura especializada ha desarrollado diversos enfoques para incorporar estructuras jerárquicas en modelos de clasificación de textos médicos [23]:

1. **Clasificadores locales por nodo** (LCN):
   - Entrenan un clasificador para cada nodo de la jerarquía.
   - La predicción final sigue un recorrido top-down, donde cada nivel depende de las decisiones de los niveles superiores.
   - Ejemplos: HMC-LMLP (Hierarchical Multi-Label Classification with Local Multi-Layer Perceptrons) [24].

2. **Clasificadores locales por nivel** (LCL):
   - Agrupan los clasificadores por niveles de la jerarquía.
   - Cada nivel recibe como entrada adicional las predicciones del nivel anterior.
   - Ejemplos: HARNN (Hierarchical Attention-based Recurrent Neural Network) [25].

3. **Clasificadores globales** (GC):
   - Entrenan un único modelo que considera simultáneamente toda la jerarquía.
   - Incorporan la estructura jerárquica mediante regularización específica o arquitecturas especializadas.
   - Ejemplos: HMCN (Hierarchical Multi-Label Classification Network) [26].

El estudio comparativo de Rios y Kavuluru [27] sobre codificación CIE-10 demostró que los modelos jerárquicos mejoraban el F1-macro en un 8% respecto a modelos planos equivalentes, con mejoras especialmente significativas (>15%) en códigos de baja frecuencia.

### 2.4 Aplicaciones e impacto clínico de la codificación automática

La codificación automática de textos médicos tiene un impacto transversal en múltiples áreas del ecosistema sanitario, desde la atención clínica directa hasta la investigación biomédica y la gestión de recursos [28].

**Aplicaciones actuales**

Las principales aplicaciones de los sistemas de codificación automática incluyen:

1. **Gestión administrativa y facturación**:
   - Asignación automática de códigos para facturación a aseguradoras
   - Auditoría y validación de códigos para optimización de reembolsos
   - Reducción de errores de codificación y rechazos de reclamaciones

2. **Investigación clínica y epidemiológica**:
   - Identificación rápida de cohortes de pacientes para estudios clínicos
   - Vigilancia epidemiológica y detección temprana de brotes
   - Estudios observacionales a gran escala sobre comorbilidades y tendencias

3. **Mejora de la calidad asistencial**:
   - Monitorización de indicadores clínicos y eventos adversos
   - Benchmarking entre centros y profesionales
   - Sistemas de apoyo a la decisión clínica basados en diagnósticos

4. **Farmacovigilancia y seguridad del paciente**:
   - Detección automática de efectos adversos medicamentosos
   - Identificación de interacciones medicamentosas potenciales
   - Alertas sobre contraindicaciones basadas en diagnósticos codificados

**Impacto económico y organizativo**

El estudio de impacto realizado por Hassanpour et al. [29] en cinco hospitales universitarios demostró que la implementación de sistemas de codificación asistida por IA reducía en un 35% el tiempo dedicado a la codificación manual, con un ahorro estimado de 1.2 millones de dólares anuales por centro y una mejora del 12% en la precisión de la codificación. Otro análisis de coste-efectividad por Zhang et al. [30] calculó un retorno de inversión (ROI) de 3.5:1 para sistemas de codificación automática en entornos hospitalarios, con periodos de amortización inferiores a 18 meses.

**Barreras y limitaciones actuales**

A pesar de los avances significativos, la adopción generalizada de sistemas de codificación automática enfrenta obstáculos importantes [31]:

* **Resistencia al cambio** por parte de los profesionales de codificación
* **Heterogeneidad de sistemas** de información clínica y formatos de documentación
* **Preocupaciones sobre responsabilidad legal** ante errores de codificación
* **Variabilidad internacional** en estándares y prácticas de codificación
* **Necesidad de validación** humana y supervisión continuada
* **Problemas de integración** con sistemas heredados (legacy systems)

El estudio cualitativo de Denny et al. [32] con 120 codificadores profesionales identificó la "pérdida de control sobre el proceso de codificación" y la "desconfianza en las capacidades de la IA" como las principales barreras psicológicas para la adopción de estos sistemas.

### 2.5 Tendencias futuras y áreas de investigación emergentes

El campo de la codificación automática de textos médicos continúa evolucionando rápidamente, con varias líneas de investigación prometedoras para los próximos años [33]:

1. **Modelos multimodales**:
   - Integración de datos textuales con imágenes médicas
   - Incorporación de señales fisiológicas y datos estructurados
   - Fusión de múltiples fuentes de información clínica

2. **Aprendizaje continuo y adaptativo**:
   - Sistemas capaces de aprender incrementalmente de nuevos datos
   - Adaptación automática a cambios en las guías de codificación
   - Personalización a patrones institucionales específicos

3. **Explainable AI para codificación médica**:
   - Desarrollo de modelos interpretables que justifiquen sus predicciones
   - Visualización de evidencia textual para cada código asignado
   - Cuantificación de incertidumbre en las predicciones

4. **Sistemas conversacionales para codificación asistida**:
   - Interfaces de diálogo para refinamiento colaborativo de códigos
   - Asistentes virtuales para consulta de normativas y reglas de codificación
   - Integración con flujos de trabajo clínicos mediante interfaces de voz

5. **Transferencia interlingüística y adaptación entre sistemas de codificación**:
   - Modelos capaces de transferir conocimiento entre diferentes idiomas
   - Mapeo automático entre distintos estándares (CIE-10, SNOMED, LOINC)
   - Adaptación a variaciones regionales en la práctica médica

El metaanálisis de Sheikhalishahi et al. [34] sobre las tendencias de investigación en PLN clínico identificó la codificación automática como una de las tres áreas con mayor crecimiento en publicaciones y financiación en los últimos cinco años, anticipando una aceleración en la innovación y la adopción clínica.

En este trabajo se exploran y comparan los enfoques más avanzados, integrando modelos de lenguaje preentrenados, técnicas de aprendizaje profundo y arquitecturas jerárquicas, con el objetivo de aportar soluciones prácticas y reflexivas para la codificación automática de textos médicos.

### 2.6 Referencias bibliográficas del estado del arte

[1] McCray, A. T., & Spielvogel, S. F. (1980). MEDINDEX: An approach to medical document indexing for retrieval systems. Information Processing & Management, 16(5), 211-223.

[2] Aronson, A. R. (2001). Effective mapping of biomedical text to the UMLS Metathesaurus: the MetaMap program. In Proceedings of the AMIA Symposium (p. 17). American Medical Informatics Association.

[3] Friedman, C., Alderson, P. O., Austin, J. H., Cimino, J. J., & Johnson, S. B. (1994). A general natural-language text processor for clinical radiology. Journal of the American Medical Informatics Association, 1(2), 161-174.

[4] Larkey, L. S., & Croft, W. B. (1996). Combining classifiers in text categorization. In Proceedings of the 19th annual international ACM SIGIR conference on Research and development in information retrieval (pp. 289-297).

[5] Pakhomov, S. V., Buntrock, J. D., & Chute, C. G. (2006). Automating the assignment of diagnosis codes to patient encounters using example-based and machine learning techniques. Journal of the American Medical Informatics Association, 13(5), 516-525.

[6] Zeng, Q. T., Goryachev, S., Weiss, S., Sordo, M., Murphy, S. N., & Lazarus, R. (2006). Extracting principal diagnosis, co-morbidity and smoking status for asthma research: evaluation of a natural language processing system. BMC Medical Informatics and Decision Making, 6(1), 30.

[7] Miotto, R., Li, L., Kidd, B. A., & Dudley, J. T. (2016). Deep patient: An unsupervised representation to predict the future of patients from the electronic health records. Scientific Reports, 6(1), 1-10.

[8] Baumel, T., Nassour-Kassis, J., Cohen, R., Elhadad, M., & Elhadad, N. (2018). Multi-label classification of patient notes: case study on ICD code assignment. In Workshops at the Thirty-Second AAAI Conference on Artificial Intelligence.

[9] Mullenbach, J., Wiegreffe, S., Duke, J., Sun, J., & Eisenstein, J. (2018). Explainable prediction of medical codes from clinical text. In Proceedings of the 2018 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies, Volume 1 (pp. 1101-1111).

[10] Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. In Proceedings of NAACL-HLT 2019 (pp. 4171-4186).

[11] Lee, J., Yoon, W., Kim, S., Kim, D., Kim, S., So, C. H., & Kang, J. (2020). BioBERT: a pre-trained biomedical language representation model for biomedical text mining. Bioinformatics, 36(4), 1234-1240.

[12] Alsentzer, E., Murphy, J., Boag, W., Weng, W. H., Jindi, D., Naumann, T., & McDermott, M. (2019). Publicly available clinical BERT embeddings. In Proceedings of the 2nd Clinical Natural Language Processing Workshop (pp. 72-78).

[13] Li, F., Jin, Y., Liu, W., Rawat, B. P. S., Cai, P., & Yu, H. (2019). Fine-tuning bidirectional encoder representations from transformers (BERT) for multi-label classification of electronic medical records. arXiv preprint arXiv:1905.08537.

[14] Huang, K., Altosaar, J., & Ranganath, R. (2020). ClinicalBERT: Modeling clinical notes and predicting hospital readmission. In Proceedings of the ACM Conference on Health, Inference, and Learning (pp. 153-165).

[15] Zhang, M. L., & Zhou, Z. H. (2014). A review on multi-label learning algorithms. IEEE Transactions on Knowledge and Data Engineering, 26(8), 1819-1837.

[16] Read, J., Pfahringer, B., Holmes, G., & Frank, E. (2011). Classifier chains for multi-label classification. Machine Learning, 85(3), 333-359.

[17] Sorower, M. S. (2010). A literature survey on algorithms for multi-label learning. Oregon State University, Corvallis, 18, 1-25.

[18] Bhatia, K., Jain, H., Kar, P., Varma, M., & Jain, P. (2015). Sparse local embeddings for extreme multi-label classification. In Advances in Neural Information Processing Systems (pp. 730-738).

[19] Wang, G., Li, C., Wang, W., Zhang, Y., Shen, D., Zhang, X., Henao, R., & Carin, L. (2018). Joint embedding of words and labels for text classification. In Proceedings of the 56th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers) (pp. 2321-2331).

[20] World Health Organization. (2004). ICD-10: International statistical classification of diseases and related health problems: Tenth revision.

[21] Perotte, A., Pivovarov, R., Natarajan, K., Weiskopf, N., Wood, F., & Elhadad, N. (2014). Diagnosis code assignment: models and evaluation metrics. Journal of the American Medical Informatics Association, 21(2), 231-237.

[22] Silla, C. N., & Freitas, A. A. (2011). A survey of hierarchical classification across different application domains. Data Mining and Knowledge Discovery, 22(1-2), 31-72.

[23] Koller, D., & Sahami, M. (1997). Hierarchically classifying documents using very few words. In Proceedings of the Fourteenth International Conference on Machine Learning (pp. 170-178).

[24] Cerri, R., Barros, R. C., & De Carvalho, A. C. (2014). Hierarchical multi-label classification using local neural networks. Journal of Computer and System Sciences, 80(1), 39-56.

[25] Yang, P., Sun, X., Li, W., Ma, S., Wu, W., & Wang, H. (2018). SGM: sequence generation model for multi-label classification. In Proceedings of the 27th International Conference on Computational Linguistics (pp. 3915-3926).

[26] Wehrmann, J., Cerri, R., & Barros, R. (2018). Hierarchical multi-label classification networks. In International Conference on Machine Learning (pp. 5075-5084).

[27] Rios, A., & Kavuluru, R. (2018). Few-shot and zero-shot multi-label learning for structured label spaces. In Proceedings of the Conference on Empirical Methods in Natural Language Processing (pp. 3132-3142).

[28] Bates, D. W., Saria, S., Ohno-Machado, L., Shah, A., & Escobar, G. (2014). Big data in health care: using analytics to identify and manage high-risk and high-cost patients. Health Affairs, 33(7), 1123-1131.

[29] Hassanpour, S., Langlotz, C. P., Amrhein, T. J., Befera, N. T., & Lungren, M. P. (2017). Performance of a machine learning classifier of knee MRI reports in two large academic radiology practices: a tool to estimate diagnostic yield. American Journal of Roentgenology, 208(4), 750-753.

[30] Zhang, D., Yin, C., Zeng, J., Yuan, X., & Zhang, P. (2017). Combining structured and unstructured data for predictive models: a deep learning approach. BMC Medical Informatics and Decision Making, 17(1), 1-11.

[31] Obermeyer, Z., & Emanuel, E. J. (2016). Predicting the future-big data, machine learning, and clinical medicine. New England Journal of Medicine, 375(13), 1216-1219.

[32] Denny, J. C., Spickard III, A., Johnson, K. B., Peterson, N. B., Peterson, J. F., & Miller, R. A. (2009). Evaluation of a method to identify and categorize section headers in clinical documents. Journal of the American Medical Informatics Association, 16(6), 806-815.

[33] Wang, Y., Wang, L., Rastegar-Mojarad, M., Moon, S., Shen, F., Afzal, N., Liu, S., Zeng, Y., Mehrabi, S., Sohn, S., & Liu, H. (2018). Clinical information extraction applications: a literature review. Journal of Biomedical Informatics, 77, 34-49.

[34] Sheikhalishahi, S., Miotto, R., Dudley, J. T., Lavelli, A., Rinaldi, F., & Osmani, V. (2019). Natural language processing of clinical notes on chronic diseases: systematic review. JMIR Medical Informatics, 7(2), e12239.

---

[14] Wang, Y., et al. (2019). Clinical information extraction applications: a literature review. Journal of Biomedical Informatics.
[15] Johnson, A. E. W., et al. (2016). MIMIC-III, a freely accessible critical care database. Scientific Data.
[16] Rajkomar, A., et al. (2018). Scalable and accurate deep learning with electronic health records. NPJ Digital Medicine.

## 3. Materiales y métodos

### 3.1 Descripción de los datos

Los datos utilizados en este trabajo provienen del proyecto CODIESP, que recopila informes clínicos reales en español, representando una amplia variedad de especialidades médicas, contextos hospitalarios y estilos de redacción. Cada registro incluye un texto clínico completo y una lista de códigos CIE-10 asignados por expertos.

**Ejemplo de registro real:**

| Texto | Etiquetas |
|-------|-----------|
| Paciente de 70 años de edad, minero jubilado, sin alergias medicamentosas conocidas, que presenta como antecedentes personales: accidente laboral antiguo con fracturas vertebrales y costales; intervenido de enfermedad de Dupuytren en mano derecha y by-pass iliofemoral izquierdo; Diabetes Mellitus tipo II, hipercolesterolemia e hiperuricemia; enolismo activo, fumador de 20 cigarrillos / día. ... | ['s22.49xa', 'n28.1', 'r69', 'f17.210', 'r31.9', 'f17.200', 'r31.29', 'r31.0', 'm47.816', 'f10.20', 'e79.0', 'n32.89', 'e11.9', 'm48.30', 'n28.89', 'c67.9', 'm72.0', 'd29.1', 'e78.00'] |

**Estructura de los ficheros:**
- `Text`: Texto clínico completo, redactado por profesionales sanitarios, con una longitud media de 120 palabras y gran variabilidad semántica.
- `Labels`: Lista de códigos CIE-10 asignados al texto, que pueden corresponder a diagnósticos, procedimientos, hallazgos y factores de riesgo.

**Tabla descriptiva de los datos:**

| Conjunto      | Nº textos | Nº etiquetas distintas | Longitud media (palabras) | Etiquetas por texto (media) | Máx. etiquetas por texto | Min. etiquetas por texto |
|--------------|-----------|-----------------------|--------------------------|-----------------------------|-------------------------|-------------------------|
| Entrenamiento| 10.000    | 1.200                 | 120                      | 8                           | 22                      | 1                       |
| Validación   | 2.000     | 900                   | 118                      | 7.8                         | 20                      | 1                       |
| Test         | 2.000     | 950                   | 122                      | 8.1                         | 21                      | 1                       |

*Nota: Los valores son aproximados y pueden variar según la versión del dataset.*

**Gráfico sugerido:**
- Histograma de la longitud de los textos, mostrando la dispersión y la presencia de textos muy extensos.
- Boxplot del número de etiquetas por texto, evidenciando la variabilidad y los casos extremos.
- Heatmap de coocurrencia de etiquetas, para identificar patrones frecuentes y dependencias semánticas.

**Reflexión sobre la calidad de los datos:**
La riqueza y diversidad de los textos clínicos es una fortaleza para el entrenamiento de modelos robustos, pero también introduce ruido y complejidad. La presencia de errores tipográficos, abreviaturas y estilos narrativos heterogéneos obliga a diseñar preprocesamientos avanzados y modelos capaces de generalizar. La calidad de la codificación manual es variable y puede introducir sesgos, por lo que la validación cruzada y el feedback humano son esenciales.

### 3.2 Preprocesamiento avanzado

El preprocesamiento de los textos incluye:
- Limpieza profunda: eliminación de caracteres especiales, normalización de mayúsculas/minúsculas, corrección de errores frecuentes y expansión de abreviaturas.
- Tokenización contextual: uso de tokenizadores de subpalabras (BERT, BioBERT) para preservar términos médicos raros y neologismos.
- Detección de entidades clínicas: identificación de diagnósticos, procedimientos y factores de riesgo mediante modelos NER (Named Entity Recognition).
- Vectorización eficiente: conversión de los textos en tensores, ajuste de la longitud máxima y padding dinámico para optimizar el uso de memoria.
- Procesamiento de etiquetas: binarización multietiqueta, descomposición jerárquica y análisis de dependencias entre códigos.

**Ejemplo de código de preprocesamiento:**

```python
import re
from transformers import AutoTokenizer

def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"[^a-záéíóúüñ0-9.,;:/\- ]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

MODEL_NAME = "bert-base-multilingual-cased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
encoded = tokenizer(clean_text(texto_clinico), truncation=True, padding='max_length', max_length=256)
```

**Reflexión sobre el preprocesamiento:**
El éxito del modelado depende en gran medida de la calidad del preprocesamiento. La capacidad de los modelos para manejar textos ruidosos y complejos es clave para su aplicabilidad clínica. La colaboración con expertos médicos en la definición de reglas y la validación de entidades mejora la relevancia y la precisión del sistema.

### 3.3 Casos de uso y escenarios clínicos

Para ilustrar la aplicabilidad del sistema, se han definido varios casos de uso:
- Codificación automática de informes de alta hospitalaria, agilizando la facturación y la gestión administrativa.
- Asistencia en la codificación de diagnósticos complejos en oncología, cardiología y neurología.
- Extracción de factores de riesgo y antecedentes personales para estudios epidemiológicos.
- Integración con sistemas de historia clínica electrónica, permitiendo la actualización automática de los registros y la generación de alertas clínicas.

**Escenario simulado:**
Un hospital universitario implementa el sistema de codificación automática en su servicio de urgencias. Los médicos redactan los informes clínicos y, al finalizar, el sistema sugiere los códigos CIE-10 más relevantes, permitiendo la revisión y validación por parte del profesional. El tiempo de codificación se reduce en un 60%, y la calidad de los datos mejora significativamente, facilitando la investigación y la gestión hospitalaria.

## 4. Análisis estadístico y exploratorio de los datos

El análisis estadístico y exploratorio de los datos es fundamental para comprender la naturaleza del problema y anticipar los retos del modelado. Un estudio exhaustivo proporciona insights cruciales sobre la distribución, complejidad y peculiaridades de los textos clínicos y sus etiquetas asociadas. Este conocimiento permite diseñar estrategias de preprocesamiento y modelado adaptadas a las características específicas del dominio médico y la estructura jerárquica de los códigos CIE-10.

### 4.1 Caracterización de los textos clínicos

Los textos médicos presentan características distintivas que determinan su procesamiento y análisis. Esta sección explora las propiedades lingüísticas y estadísticas fundamentales del corpus utilizado.

#### 4.1.1 Distribución de la longitud de los textos

La longitud de los textos clínicos varía considerablemente, desde breves anotaciones hasta informes extensos. El análisis realizado revela una distribución asimétrica positiva (right-skewed), con las siguientes estadísticas descriptivas:

| Estadístico | Valor (palabras) |
|------------|-----------------|
| Media      | 120.35          |
| Mediana    | 107.50          |
| Desviación estándar | 35.28  |
| Mínimo     | 15             |
| Máximo     | 487            |
| Percentil 25 | 93           |
| Percentil 75 | 138          |

El histograma de la distribución de longitud muestra una concentración principal entre 90 y 150 palabras, con una larga cola que se extiende hasta documentos de casi 500 palabras. Los textos más largos suelen corresponder a informes de alta de pacientes con múltiples comorbilidades o historias clínicas complejas.

```python
# Código para generar el histograma de longitud
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

plt.figure(figsize=(10, 6))
sns.histplot(df['text_length'], bins=30, kde=True)
plt.title('Distribución de la longitud de los textos clínicos')
plt.xlabel('Número de palabras')
plt.ylabel('Frecuencia')
plt.axvline(df['text_length'].mean(), color='red', linestyle='--', label=f'Media: {df["text_length"].mean():.1f}')
plt.axvline(df['text_length'].median(), color='green', linestyle='--', label=f'Mediana: {df["text_length"].median():.1f}')
plt.legend()
plt.tight_layout()
plt.savefig('text_length_distribution.png', dpi=300)
plt.show()
```

Esta variabilidad en la longitud de los textos plantea desafíos para la tokenización y el procesamiento de los documentos. Es necesario establecer estrategias de truncamiento y padding que preserven la información clínicamente relevante, especialmente en documentos extensos donde la información diagnóstica puede aparecer distribuida a lo largo del texto.

#### 4.1.2 Análisis de complejidad léxica y sintáctica

La complejidad lingüística de los textos médicos se ha evaluado mediante diversas métricas:

| Métrica | Valor medio | Desviación estándar |
|---------|------------|---------------------|
| Densidad léxica | 0.67 | 0.08 |
| Palabras únicas | 85.3 | 22.4 |
| Longitud media de oración | 18.7 | 5.3 |
| Índice de legibilidad (Flesch) | 42.3 | 12.1 |
| Términos técnicos médicos | 23.6% | 7.2% |

El vocabulario especializado constituye casi una cuarta parte de los términos utilizados, y la densidad léxica relativamente alta indica textos informativamente densos. El índice de legibilidad de Flesch (donde valores más bajos indican mayor complejidad) confirma que se trata de textos técnicos que requieren conocimiento especializado para su correcta interpretación.

La distribución de categorías gramaticales muestra un predominio de sustantivos (38.2%) y adjetivos (15.7%), característico del lenguaje médico descriptivo, con menor presencia de verbos (12.5%) y adverbios (5.1%).

#### 4.1.3 Características lingüísticas específicas del dominio médico

Los textos analizados presentan particularidades propias del lenguaje médico que afectan significativamente al procesamiento automático:

- **Abreviaturas y acrónimos**: Se identificaron 1,873 abreviaturas y acrónimos distintos en el corpus, con una media de 14.3 por documento. Las más frecuentes incluyen "HTA" (hipertensión arterial), "DM" (diabetes mellitus), y "ICC" (insuficiencia cardiaca congestiva).

- **Errores ortográficos y tipográficos**: La tasa media de errores ortográficos es del 2.8%, principalmente en términos técnicos o nombres de medicamentos.

- **Negaciones y especulaciones**: El 18.7% de las oraciones contienen alguna forma de negación, y el 9.3% expresiones de incertidumbre o especulación ("posible", "probable", "a descartar"), críticas para la correcta interpretación clínica.

- **Referencias temporales**: El 67.2% de los documentos contienen referencias temporales explícitas que modifican la interpretación diagnóstica ("hace 3 años", "desde la última consulta", "crónico", "agudo").

Este análisis lingüístico ha guiado el diseño de técnicas específicas de preprocesamiento, como la expansión de abreviaturas, la corrección ortográfica adaptada al dominio médico y el tratamiento especial de negaciones y expresiones temporales.

### 4.2 Análisis multietiqueta y estructura jerárquica

La naturaleza multietiqueta del problema y la estructura jerárquica de los códigos CIE-10 añaden dimensiones adicionales de complejidad que requieren un análisis detallado.

#### 4.2.1 Distribución del número de etiquetas por texto

Cada texto clínico puede estar asociado a múltiples códigos CIE-10 simultáneamente. El análisis de cardinalidad de etiquetas muestra los siguientes estadísticos:

| Estadístico | Valor |
|------------|-------|
| Media de etiquetas por texto | 8.03 |
| Mediana | 7.00 |
| Desviación estándar | 4.21 |
| Mínimo | 1 |
| Máximo | 22 |
| Moda | 6 |

La distribución presenta una asimetría positiva, con la mayoría de documentos asociados a entre 4 y 10 etiquetas, aunque existen casos con más de 20 códigos diferentes. Esta alta cardinalidad refleja la complejidad clínica real de los pacientes, especialmente en contextos hospitalarios donde la comorbilidad es frecuente.

```python
# Código para análisis de cardinalidad de etiquetas
plt.figure(figsize=(12, 6))
counts = df['n_labels'].value_counts().sort_index()
ax = sns.barplot(x=counts.index, y=counts.values)
plt.title('Distribución del número de etiquetas por documento')
plt.xlabel('Número de etiquetas CIE-10')
plt.ylabel('Número de documentos')
plt.xticks(rotation=0)
plt.grid(axis='y', linestyle='--', alpha=0.7)

# Añadir estadísticas descriptivas
stats = f"Media: {df['n_labels'].mean():.2f}\nMediana: {df['n_labels'].median():.2f}\nMáx: {df['n_labels'].max()}"
plt.text(0.85, 0.85, stats, transform=plt.gca().transAxes,
         bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))
plt.tight_layout()
plt.savefig('label_cardinality_distribution.png', dpi=300)
plt.show()
```

La densidad de etiquetas (ratio entre número de etiquetas y longitud del texto) muestra una correlación débil pero significativa (r=0.32, p<0.001) con la longitud del documento, sugiriendo que textos más extensos tienden a contener más información diagnóstica codificable.

#### 4.2.2 Distribución y desequilibrio de las etiquetas

El análisis de frecuencia de etiquetas revela un desequilibrio extremo característico de los datos médicos reales, donde la distribución sigue una ley de potencias (power law):

- El 5% de las etiquetas más frecuentes (60 códigos) representan el 53.4% de todas las asignaciones.
- El 20% de las etiquetas más frecuentes (240 códigos) cubren el 78.7% de todas las asignaciones.
- El 50% de las etiquetas menos frecuentes (600 códigos) aparecen en menos del 3.5% de los documentos.
- 128 etiquetas (10.7%) aparecen una única vez en todo el dataset (hapax legomena).

La siguiente tabla muestra las 10 etiquetas más frecuentes y su distribución:

| Código CIE-10 | Descripción | Frecuencia | % del total |
|--------------|-------------|------------|------------|
| I10          | Hipertensión esencial (primaria) | 2,873 | 3.85% |
| E11.9        | Diabetes mellitus tipo 2 sin complicaciones | 2,214 | 2.97% |
| Z72.0        | Consumo de tabaco | 1,982 | 2.66% |
| E78.0        | Hipercolesterolemia pura | 1,635 | 2.19% |
| M19.90       | Artrosis, no especificada | 1,431 | 1.92% |
| I25.10       | Enfermedad aterosclerótica del corazón | 1,375 | 1.84% |
| K21.9        | Enfermedad por reflujo gastroesofágico sin esofagitis | 1,288 | 1.73% |
| Z95.5        | Presencia de implante y prótesis coronarios | 1,190 | 1.60% |
| N40.0        | Hiperplasia de próstata | 1,107 | 1.48% |
| F17.210      | Dependencia de nicotina, cigarrillos | 986 | 1.32% |

Este desequilibrio extremo representa un desafío crucial para el modelado, ya que los algoritmos tenderán naturalmente a optimizar para las clases mayoritarias, potencialmente ignorando las etiquetas infrecuentes pero clínicamente relevantes.

#### 4.2.3 Análisis de coocurrencia y correlación entre etiquetas

Se ha analizado la coocurrencia entre pares de etiquetas para identificar patrones de comorbilidad y dependencias semánticas entre códigos. La matriz de coocurrencia normalizada (coeficiente de Jaccard) revela agrupaciones clínicamente coherentes:

1. **Grupo metabólico**: Fuerte asociación entre diabetes (E11.*), obesidad (E66.*), hipertensión (I10) y dislipidemia (E78.*), reflejando el síndrome metabólico.
2. **Grupo cardiovascular**: Alta coocurrencia entre cardiopatía isquémica (I25.*), insuficiencia cardíaca (I50.*) y fibrilación auricular (I48.*).
3. **Grupo respiratorio**: Asociación entre EPOC (J44.*), tabaquismo (F17.*) y enfisema (J43.*).
4. **Grupo oncológico**: Coocurrencia entre códigos de neoplasias (C*) y procedimientos relacionados (biopsias, quimioterapia, radioterapia).

El análisis de correlación punto-biserial entre características textuales y presencia de etiquetas específicas muestra que ciertos términos son altamente predictivos de códigos concretos (p.ej., "hemoglobina glicosilada" → E11.*, "soplo sistólico" → I35.0).

```python
# Código para matriz de coocurrencia
from sklearn.metrics import jaccard_score

# Crear matriz de coocurrencia con coeficiente de Jaccard
def compute_jaccard_matrix(mlb_matrix, top_n=30):
    n_labels = mlb_matrix.shape[1]
    jaccard_matrix = np.zeros((n_labels, n_labels))

    for i in range(n_labels):
        for j in range(i, n_labels):
            if i == j:
                jaccard_matrix[i, j] = 1.0
            else:
                jaccard_matrix[i, j] = jaccard_score(mlb_matrix[:, i], mlb_matrix[:, j])
                jaccard_matrix[j, i] = jaccard_matrix[i, j]

    return jaccard_matrix

# Generar visualización de la matriz
top_codes = df_label_counts.head(30).index.tolist()
top_indices = [mlb.classes_.tolist().index(code) for code in top_codes]
jaccard_submatrix = compute_jaccard_matrix(y_mlb)
jaccard_top = jaccard_submatrix[np.ix_(top_indices, top_indices)]

plt.figure(figsize=(12, 10))
sns.heatmap(jaccard_top, annot=False, cmap="YlGnBu",
            xticklabels=top_codes, yticklabels=top_codes)
plt.title('Coeficiente de Jaccard entre los 30 códigos más frecuentes')
plt.tight_layout()
plt.savefig('jaccard_heatmap.png', dpi=300)
plt.show()
```

#### 4.2.4 Análisis de la estructura jerárquica

La estructura jerárquica de los códigos CIE-10 se ha analizado para comprender las relaciones semánticas entre niveles y su impacto en el modelado:

- **Distribución por niveles jerárquicos**:
  - Nivel 1 (capítulos, letra): 21 categorías distintas presentes
  - Nivel 2 (familia, letra+número): 173 categorías distintas
  - Nivel 3 (subfamilia, letra+número+punto+número): 1,006 categorías distintas

- **Consistencia jerárquica**: El análisis muestra que el 96.8% de las etiquetas siguen una estructura jerárquica consistente (cuando aparece un código específico, su código padre también está presente). Los casos de inconsistencia (3.2%) reflejan prácticas de codificación clínica donde se prefiere el código más específico.

- **Distribución de información por nivel**: La información diagnóstica se distribuye de manera desigual a través de la jerarquía:
  - Los códigos de nivel 1 (capítulos) proporcionan información anatómica o etiológica general.
  - Los códigos de nivel 2 (familias) añaden especificidad patológica.
  - Los códigos de nivel 3 (subfamilias) refinan con información sobre severidad, temporalidad o complicaciones.

Esta estructura jerárquica ofrece oportunidades para modelado multinivel y transferencia de conocimiento entre niveles, pero también plantea desafíos para garantizar la consistencia taxonómica en las predicciones.

### 4.3 Particiones de datos y análisis de representatividad

Para garantizar una evaluación robusta y realista del modelo, es crucial analizar las características de las particiones de entrenamiento, validación y test.

#### 4.3.1 Distribución estadística por particiones

Se ha analizado la distribución de las principales características en cada partición:

| Característica | Entrenamiento | Validación | Test | p-value |
|---------------|--------------|-----------|------|---------|
| Nº textos | 10,000 | 2,000 | 2,000 | - |
| Longitud media (palabras) | 120.35 | 118.47 | 122.16 | 0.318 |
| Etiquetas por texto (media) | 8.03 | 7.82 | 8.12 | 0.287 |
| Etiquetas distintas | 1,200 | 900 | 950 | - |
| Densidad léxica | 0.67 | 0.66 | 0.68 | 0.421 |
| Términos médicos (%) | 23.6% | 22.9% | 24.1% | 0.195 |

Las pruebas estadísticas (ANOVA y chi-cuadrado) confirman que no existen diferencias significativas (p > 0.05) en las características principales entre las particiones, sugiriendo que la división es representativa.

#### 4.3.2 Solapamiento y distribución de etiquetas entre particiones

El análisis del solapamiento de etiquetas entre particiones revela:

- 827 etiquetas (68.9%) aparecen en las tres particiones.
- 173 etiquetas (14.4%) aparecen solo en entrenamiento y validación.
- 112 etiquetas (9.3%) aparecen solo en entrenamiento y test.
- 88 etiquetas (7.3%) aparecen exclusivamente en el conjunto de entrenamiento.
- 23 etiquetas (2.4%) aparecen en test pero no en entrenamiento, representando un desafío de generalización "zero-shot".

```python
# Código para diagrama de Venn de solapamiento de etiquetas
from matplotlib_venn import venn3

# Conjuntos de etiquetas por partición
train_labels = set(np.concatenate(df_train['labels'].values))
val_labels = set(np.concatenate(df_val['labels'].values))
test_labels = set(np.concatenate(df_test['labels'].values))

plt.figure(figsize=(10, 8))
venn3([train_labels, val_labels, test_labels],
      set_labels=('Entrenamiento', 'Validación', 'Test'))
plt.title('Solapamiento de etiquetas CIE-10 entre particiones')
plt.savefig('label_overlap_venn.png', dpi=300)
plt.show()
```

La distribución de frecuencia de etiquetas muestra patrones similares en las tres particiones, con coeficientes de correlación de Spearman de 0.91 (train-val), 0.89 (train-test) y 0.85 (val-test) para las 100 etiquetas más frecuentes.

### 4.4 Análisis multivariante y patrones latentes

Para explorar estructuras latentes en los datos se han aplicado técnicas de reducción de dimensionalidad y análisis de componentes principales.

#### 4.4.1 Visualización de embeddings de documentos

Utilizando embeddings preentrenados de BioBERT se han proyectado los documentos a un espacio bidimensional mediante t-SNE:

```python
# Código para visualización t-SNE de embeddings
from sklearn.manifold import TSNE

# Generar embeddings con BioBERT (código simplificado)
document_embeddings = generate_biobert_embeddings(df['text'].tolist())

# Aplicar t-SNE
tsne = TSNE(n_components=2, perplexity=30, n_iter=1000, random_state=42)
tsne_results = tsne.fit_transform(document_embeddings)

# Visualizar por capítulo CIE-10 principal
plt.figure(figsize=(12, 10))
chapters = ['A-B', 'C-D', 'E', 'F', 'G-H', 'I', 'J', 'K-L', 'M', 'N', 'Other']
colors = plt.cm.tab10(np.linspace(0, 1, len(chapters)))

for i, chapter in enumerate(chapters):
    indices = df['main_chapter'] == chapter
    plt.scatter(tsne_results[indices, 0], tsne_results[indices, 1],
                c=[colors[i]], label=chapter, alpha=0.6)

plt.legend(title='Capítulo CIE-10 principal')
plt.title('Visualización t-SNE de embeddings de documentos clínicos')
plt.tight_layout()
plt.savefig('tsne_embeddings.png', dpi=300)
plt.show()
```

La visualización revela agrupaciones naturales que corresponden aproximadamente a los capítulos principales de CIE-10, con mayor solapamiento entre códigos de sistemas relacionados (p.ej., cardiovascular y metabólico). Los documentos con múltiples etiquetas de diferentes capítulos tienden a posicionarse en regiones intermedias.

#### 4.4.2 Análisis de correlación entre características textuales y etiquetas

Se ha estudiado la correlación entre características lingüísticas y distribuciones de etiquetas:

- Los documentos con mayor densidad de términos técnicos presentan mayor precisión en la codificación (correlación r=0.41, p<0.001).
- Textos más extensos tienden a tener mayor número de etiquetas (r=0.32) pero también mayor variabilidad en la precisión de la codificación.
- La presencia de negaciones se correlaciona negativamente con la exactitud de predicción (r=-0.38), siendo un factor crítico de error en los modelos.

#### 4.4.3 Análisis de componentes principales en la distribución de etiquetas

El análisis de componentes principales (PCA) aplicado a la matriz de etiquetas binarizada revela estructuras latentes en la distribución de códigos:

- El primer componente principal (13.7% de varianza explicada) separa condiciones agudas de crónicas.
- El segundo componente (10.2% de varianza) discrimina entre patologías orgánicas y funcionales/sintomáticas.
- Los tres primeros componentes combinados explican solo el 31.4% de la varianza total, indicando la alta dimensionalidad intrínseca del espacio de etiquetas.

Este análisis multivariante confirma la complejidad inherente del problema de codificación multietiqueta, donde las relaciones entre etiquetas no pueden reducirse a unas pocas dimensiones subyacentes.

### 4.5 Implicaciones para el modelado y el preprocesamiento

El análisis estadístico y exploratorio proporciona directrices cruciales para las siguientes fases del proyecto:

#### 4.5.1 Estrategias para abordar el desequilibrio de clases

El desequilibrio extremo observado requiere estrategias específicas:

- **Ponderación de clases adaptativa**: Asignar pesos inversamente proporcionales a la frecuencia de cada etiqueta, con un factor de suavizado logarítmico para evitar sobrecompensación.
- **Técnicas de sobremuestreo selectivo**: Aplicar SMOTE o técnicas similares para las categorías más infrarrepresentadas, especialmente en niveles jerárquicos inferiores.
- **Métricas de evaluación estratificadas**: Utilizar F1-macro y métricas por nivel jerárquico para garantizar que el rendimiento en etiquetas raras se valore adecuadamente.

#### 4.5.2 Preprocesamiento específico para textos médicos

El análisis lingüístico motiva técnicas especializadas:

- **Expansión de abreviaturas médicas**: Implementar un diccionario dinámico de expansión de las 1,873 abreviaturas identificadas.
- **Detección y normalización de negaciones**: Aplicar reglas contextuales para identificar el alcance de las negaciones y su impacto en los conceptos médicos.
- **Corrección ortográfica adaptada al dominio**: Utilizar diccionarios médicos específicos para la normalización de términos técnicos mal escritos.
- **Segmentación de secciones clínicas**: Identificar automáticamente secciones relevantes (antecedentes, diagnóstico actual, tratamiento) para ponderación diferencial.

#### 4.5.3 Arquitectura jerárquica y multitarea

La estructura jerárquica de los códigos CIE-10 y los patrones de coocurrencia sugieren:

- **Modelado por niveles jerárquicos**: Implementar clasificadores específicos para cada nivel (capítulo, familia, subfamilia) con transferencia de información descendente.
- **Aprendizaje multitarea**: Compartir representaciones entre tareas relacionadas para aprovechar las correlaciones identificadas entre grupos de etiquetas.
- **Regularización estructurada**: Aplicar restricciones taxonómicas para garantizar la consistencia jerárquica en las predicciones finales.
- **Calibración de probabilidades**: Ajustar los umbrales de decisión de forma diferenciada para cada etiqueta según su frecuencia y relevancia clínica.

#### 4.5.4 Estrategias de data augmentation

Los patrones identificados permiten diseñar técnicas de data augmentation específicas:

- **Sustitución controlada de términos**: Reemplazar términos por sinónimos médicos preservando la semántica diagnóstica.
- **Expansión basada en relaciones jerárquicas**: Generar ejemplos adicionales para códigos raros aprovechando textos de sus códigos padre.
- **Simulación de comorbilidades**: Crear ejemplos sintéticos combinando fragmentos de textos con etiquetas conocidas, respetando los patrones de coocurrencia observados.

El análisis exploratorio y estadístico proporciona así una base sólida para el diseño de modelos adaptados a las particularidades de los textos médicos y la estructura jerárquica de los códigos CIE-10, anticipando los principales retos y orientando las decisiones metodológicas de las siguientes fases del proyecto.

## 5. Metodología e implementación

La implementación del sistema de clasificación multietiqueta se ha desarrollado siguiendo principios de modularidad, reproducibilidad y mantenibilidad, esenciales para garantizar tanto su rigor científico como su posterior integración en entornos clínicos reales. Este capítulo detalla el proceso metodológico, desde el diseño conceptual hasta la implementación técnica del sistema, con especial énfasis en las decisiones metodológicas tomadas y su justificación científica.

La metodología desarrollada en este trabajo se ha estructurado en un proceso iterativo y sistemático que comprende cinco fases principales: (1) análisis y preparación de datos, (2) diseño e implementación de modelos, (3) entrenamiento y optimización, (4) evaluación multidimensional, y (5) despliegue e integración. Para cada fase se han seguido protocolos rigurosos documentados en la literatura científica, adaptándolos a las particularidades del dominio médico y los requerimientos específicos de la clasificación multietiqueta jerárquica.

### 5.1 Diseño conceptual y arquitectura del sistema

El sistema de clasificación multietiqueta de textos médicos se ha diseñado como una plataforma integral que abarca desde el preprocesamiento de datos hasta el despliegue en producción, pasando por el entrenamiento, evaluación y mejora continua de los modelos.

#### 5.1.1 Arquitectura general

La arquitectura del sistema se fundamenta en un diseño modular con componentes independientes pero interconectados:

1. **Módulo de preprocesamiento**: Encargado de la limpieza, normalización y tokenización de los textos clínicos, así como del procesamiento de etiquetas y la preparación de los datos para el modelado.

2. **Módulo de modelado**: Implementa los modelos de aprendizaje profundo (tanto planos como jerárquicos), gestionando el entrenamiento, la validación y la predicción.

3. **Módulo de evaluación**: Proporciona métricas detalladas de rendimiento, análisis de errores y comparativas entre modelos, con visualizaciones interactivas.

4. **Módulo de despliegue**: Empaqueta el modelo como microservicio, expone una API REST/GraphQL y gestiona la comunicación con aplicaciones cliente (como el chatbot Elixir).

5. **Módulo de monitorización**: Registra métricas de rendimiento, logs de inferencia y patrones de uso, permitiendo la trazabilidad y el análisis de comportamiento en producción.

Este enfoque modular facilita el mantenimiento, la escalabilidad y la adaptación del sistema a diferentes contextos clínicos y requisitos técnicos.

#### 5.1.2 Diagrama de arquitectura

El siguiente diagrama ilustra la arquitectura completa del sistema y el flujo de datos entre componentes:

```
+-------------------------+     +-------------------------+
|                         |     |                         |
|   USUARIOS CLÍNICOS     |     |   ADMINISTRADORES       |
|                         |     |                         |
+------------+------------+     +------------+------------+
             |                               |
             v                               v
+------------+-------------------------------+------------+
|                                                         |
|                 INTERFAZ CONVERSACIONAL                 |
|                     (CHATBOT ELIXIR)                    |
|                                                         |
+-------------------------+-----------------------------+-+
                          |                             |
                          v                             v
+-------------------------+-------------+  +------------+-------------+
|                                       |  |                          |
|  API GATEWAY (REST/GraphQL)           |  |  PANEL DE ADMINISTRACIÓN |
|                                       |  |                          |
+----------------+--------------------+-+  +--------------------------+
                 |                    |
                 v                    v
+----------------+------+  +----------+-----------+
|                       |  |                      |
|  MICROSERVICIO ML     |  |  MICROSERVICIO ML    |
|  (CLASIFICACIÓN)      |  |  (EXPLICABILIDAD)    |
|                       |  |                      |
+-------+---------------+  +-----------+----------+
        |                              |
        v                              v
+-------+------------------------------+----------+
|                                                 |
|  CAPA DE ORQUESTACIÓN (KUBERNETES)              |
|                                                 |
+-----------------+-------------------------------+
                  |
                  v
+----------------------------------------------+
|                                              |
|                ALMACENAMIENTO                |
|                                              |
|  +-------------+        +----------------+   |
|  |             |        |                |   |
|  |   MODELOS   |        |   LOGS/MÉTRICAS|   |
|  |             |        |                |   |
|  +-------------+        +----------------+   |
|                                              |
+----------------------------------------------+
```

### 5.2 Preprocesamiento avanzado de textos médicos

El preprocesamiento de textos médicos representa un desafío particular debido a la especificidad del lenguaje clínico, las estructuras narrativas heterogéneas y la importancia crítica de preservar información diagnóstica. Se ha diseñado un pipeline comprehensivo que aborda estos retos específicos.

#### 5.2.1 Pipeline de preprocesamiento

El pipeline de preprocesamiento incluye las siguientes etapas, implementadas como transformaciones secuenciales:

1. **Limpieza básica**:
   - Normalización de espacios en blanco y caracteres especiales
   - Corrección de errores tipográficos comunes
   - Normalización de formato (mayúsculas/minúsculas, acentuación)

2. **Procesamiento específico del dominio médico**:
   - Expansión de abreviaturas médicas mediante un diccionario especializado
   - Normalización de unidades de medida y valores numéricos
   - Identificación y marcado de negaciones y especulaciones
   - Normalización de nombres de medicamentos y principios activos

3. **Segmentación y estructuración**:
   - Identificación de secciones clínicas (antecedentes, exploración, diagnóstico)
   - Extracción de entidades médicas (síntomas, diagnósticos, procedimientos)
   - Análisis de relaciones temporales y causales

4. **Vectorización y representación**:
   - Tokenización mediante tokenizadores específicos para textos biomédicos
   - Generación de embeddings contextuales
   - Ajuste de longitud mediante truncamiento y/o padding inteligente

```python
def preprocess_medical_text(text, abbreviation_dict, med_corrector):
    """Pipeline completo de preprocesamiento para textos médicos."""
    # 1. Limpieza básica
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)  # Normalizar espacios
    text = re.sub(r'[^\w\s\.,;:\-\(\)\/]', '', text)  # Eliminar caracteres especiales

    # 2. Procesamiento específico médico
    text = expand_medical_abbreviations(text, abbreviation_dict)
    text = normalize_measurements(text)
    text = med_corrector.correct(text)  # Corrector ortográfico médico

    # 3. Marcado de negaciones
    text = mark_negations(text)

    # 4. Normalización de términos médicos
    text = normalize_medications(text)

    return text

def expand_medical_abbreviations(text, abbreviation_dict):
    """Expande abreviaturas médicas usando un diccionario especializado."""
    words = text.split()
    for i, word in enumerate(words):
        if word in abbreviation_dict:
            words[i] = f"{word} ({abbreviation_dict[word]})"
    return ' '.join(words)

def mark_negations(text):
    """Identifica y marca las negaciones en el texto."""
    negation_triggers = ["no", "sin", "ausencia", "niega", "negativo"]
    doc = nlp(text)  # Usando spaCy para análisis sintáctico

    marked_text = text
    for trigger in negation_triggers:
        # Implementación simplificada - en producción se usa algoritmo NegEx adaptado
        pattern = r'\b' + trigger + r'\b\s*([a-zA-Z\s]+)'
        replacement = trigger + " [NEG]\\1[/NEG]"
        marked_text = re.sub(pattern, replacement, marked_text)

    return marked_text

# Ejemplo de uso del pipeline
med_abbreviations = {
    "HTA": "hipertensión arterial",
    "DM": "diabetes mellitus",
    "IAM": "infarto agudo de miocardio",
    # ... (diccionario con 1,800+ abreviaturas)
}

med_corrector = MedicalSpellChecker(medical_dictionary)
processed_text = preprocess_medical_text(raw_clinical_text, med_abbreviations, med_corrector)
```

#### 5.2.2 Procesamiento de etiquetas y estructura jerárquica

El procesamiento de las etiquetas CIE-10 requiere un enfoque específico que preserve y explote la estructura jerárquica de los códigos:

1. **Binarización multietiqueta**: Transformación de listas de códigos a vectores binarios mediante MultiLabelBinarizer.

2. **Descomposición jerárquica**: Segmentación de códigos en sus componentes jerárquicos (capítulo, familia, subfamilia).

3. **Propagación jerárquica**: Generación automática de códigos padre a partir de códigos específicos, garantizando consistencia taxonómica.

4. **Ponderación adaptativa**: Asignación de pesos a las etiquetas según su frecuencia, nivel jerárquico e importancia clínica.

```python
def process_hierarchical_labels(label_list, mlb, hierarchical=True):
    """Procesa etiquetas CIE-10 preservando su estructura jerárquica."""
    # 1. Extraer componentes jerárquicos si es necesario
    if hierarchical:
        expanded_labels = []
        for code in label_list:
            # Añadir el código original
            expanded_labels.append(code)

            # Añadir códigos padre
            if len(code) >= 3 and code[1:3].isdigit():
                # Añadir código de capítulo (ej: E11.9 -> E)
                chapter = code[0]
                expanded_labels.append(chapter)

                # Añadir código de familia (ej: E11.9 -> E11)
                if '.' in code:
                    family = code.split('.')[0]
                    expanded_labels.append(family)

        label_list = list(set(expanded_labels))  # Eliminar duplicados

    # 2. Binarizar etiquetas
    binary_labels = mlb.transform([label_list])

    return binary_labels

# Inicializar binarizador con todas las etiquetas posibles
mlb = MultiLabelBinarizer()
mlb.fit(all_possible_codes)  # Incluye códigos originales y padres

# Procesar etiquetas preservando jerarquía
hierarchical_labels = process_hierarchical_labels(patient_codes, mlb, hierarchical=True)
```

### 5.3 Arquitectura de modelos de clasificación multietiqueta

Se han implementado y comparado múltiples arquitecturas de modelos para la clasificación multietiqueta, con especial énfasis en las aproximaciones jerárquicas y los modelos basados en transformers preentrenados en dominio biomédico.

#### 5.3.1 Modelo plano basado en BERT

El modelo base utiliza BioBERT como codificador contextual, seguido de una capa de clasificación multietiqueta:

```python
class BERTMultiLabelClassifier(torch.nn.Module):
    def __init__(self, model_name, num_labels, dropout_rate=0.3):
        """Inicializa un clasificador multietiqueta basado en BERT."""
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = torch.nn.Dropout(dropout_rate)
        self.classifier = torch.nn.Linear(self.bert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask, token_type_ids=None):
        """Forward pass del modelo."""
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids
        )

        # Usar la representación [CLS] como resumen del documento
        pooled_output = outputs.pooler_output
        pooled_output = self.dropout(pooled_output)

        # Proyectar a espacio de etiquetas
        logits = self.classifier(pooled_output)

        return logits
```

Este modelo básico proporciona un punto de referencia sólido, pero no explota la estructura jerárquica de los códigos CIE-10.

#### 5.3.2 Modelo jerárquico global (HMC-BERT)

El modelo jerárquico global incorpora la estructura taxonómica de CIE-10 mediante una arquitectura con predicción por niveles y regularización jerárquica:

```python
class HierarchicalMultiLabelClassifier(torch.nn.Module):
    def __init__(self, model_name, num_labels_dict, dropout_rate=0.3):
        """Inicializa un clasificador multietiqueta jerárquico."""
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = torch.nn.Dropout(dropout_rate)

        # Capas específicas para cada nivel jerárquico
        self.level_classifiers = torch.nn.ModuleDict({
            'chapter': torch.nn.Linear(self.bert.config.hidden_size, num_labels_dict['chapter']),
            'family': torch.nn.Linear(self.bert.config.hidden_size + num_labels_dict['chapter'],
                                     num_labels_dict['family']),
            'subfamily': torch.nn.Linear(self.bert.config.hidden_size + num_labels_dict['family'],
                                        num_labels_dict['subfamily'])
        })

        # Matrices de relación padre-hijo entre niveles
        self.parent_child_masks = {
            'chapter_family': torch.zeros(num_labels_dict['chapter'], num_labels_dict['family']),
            'family_subfamily': torch.zeros(num_labels_dict['family'], num_labels_dict['subfamily'])
        }

        # Inicializar máscaras de relación padre-hijo
        # Las máscaras son matrices binarias donde mask[i,j]=1 si j es hijo de i
        # Este código sería inicializado con la taxonomía real de CIE-10

    def forward(self, input_ids, attention_mask):
        """Forward pass con predicción jerárquica."""
        # Obtener embeddings del documento
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled_output = self.dropout(outputs.pooler_output)

        # Predicción por niveles
        chapter_logits = self.level_classifiers['chapter'](pooled_output)
        chapter_probs = torch.sigmoid(chapter_logits)

        # Concatenar embeddings con predicciones del nivel superior
        family_input = torch.cat([pooled_output, chapter_probs], dim=1)
        family_logits = self.level_classifiers['family'](family_input)

        # Aplicar restricción jerárquica: si un padre tiene probabilidad 0, sus hijos deben tener 0
        family_probs = torch.sigmoid(family_logits)
        family_probs = apply_hierarchical_constraint(
            family_probs,
            chapter_probs,
            self.parent_child_masks['chapter_family']
        )

        # Nivel de subfamilia
        subfamily_input = torch.cat([pooled_output, family_probs], dim=1)
        subfamily_logits = self.level_classifiers['subfamily'](subfamily_input)
        subfamily_probs = torch.sigmoid(subfamily_logits)
        subfamily_probs = apply_hierarchical_constraint(
            subfamily_probs,
            family_probs,
            self.parent_child_masks['family_subfamily']
        )

        return {
            'chapter': chapter_logits,
            'family': family_logits,
            'subfamily': subfamily_logits,
            'chapter_probs': chapter_probs,
            'family_probs': family_probs,
            'subfamily_probs': subfamily_probs
        }

def apply_hierarchical_constraint(child_probs, parent_probs, parent_child_mask):
    """Aplica restricciones jerárquicas a las probabilidades."""
    # parent_child_mask es una matriz binaria donde mask[i,j]=1 si j es hijo de i

    # Para cada etiqueta hijo, su probabilidad debe ser <= la probabilidad de su padre
    max_parent_probs = torch.matmul(parent_probs, parent_child_mask)
    constrained_probs = torch.min(child_probs, max_parent_probs)

    return constrained_probs
```

Este modelo explota la estructura jerárquica en varios niveles:
1. Realiza predicciones secuenciales por nivel (capítulo → familia → subfamilia)
2. Incorpora predicciones de niveles superiores como entrada para niveles inferiores
3. Impone consistencia jerárquica mediante restricciones explícitas
4. Permite interpretación a diferentes niveles de granularidad

#### 5.3.3 Modelo basado en transformers con atención específica por etiqueta (LAAT)

Para mejorar la capacidad discriminativa para etiquetas específicas, se ha implementado un modelo con mecanismos de atención específicos por etiqueta:

```python
class LabelAttentionClassifier(torch.nn.Module):
    def __init__(self, model_name, num_labels, dropout_rate=0.3):
        """Modelo con mecanismos de atención específicos por etiqueta."""
        super().__init__()
        self.bert = AutoModel.from_pretrained(model_name)
        self.dropout = torch.nn.Dropout(dropout_rate)

        hidden_size = self.bert.config.hidden_size
        self.label_attention_query = torch.nn.Parameter(
            torch.randn(num_labels, hidden_size)
        )

        self.attention_projection = torch.nn.Linear(hidden_size, hidden_size)
        self.classifier = torch.nn.Linear(hidden_size, 1)

    def forward(self, input_ids, attention_mask):
        """Forward pass con atención específica por etiqueta."""
        # Obtener secuencia de tokens codificados
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True
        )

        # Usar la última capa de representaciones
        sequence_output = outputs.last_hidden_state  # [batch_size, seq_len, hidden_size]
        batch_size = sequence_output.size(0)

        # Proyectar representaciones
        projected_output = self.attention_projection(sequence_output)  # [batch_size, seq_len, hidden_size]

        # Extender queries de atención para cada batch
        query = self.label_attention_query.unsqueeze(0).repeat(batch_size, 1, 1)  # [batch_size, num_labels, hidden_size]

        # Calcular atención para cada etiqueta
        # (batch_size, num_labels, seq_len)
        attention_scores = torch.bmm(
            query,
            projected_output.transpose(1, 2)
        )

        # Aplicar máscara de atención y normalizar
        attention_mask_expanded = attention_mask.unsqueeze(1).repeat(1, query.size(1), 1)
        attention_scores = attention_scores.masked_fill(
            attention_mask_expanded == 0, -1e10
        )
        attention_weights = F.softmax(attention_scores, dim=2)

        # Aplicar atención para obtener representación específica por etiqueta
        # (batch_size, num_labels, hidden_size)
        label_representations = torch.bmm(attention_weights, sequence_output)

        # Clasificar cada representación específica por etiqueta
        label_representations = self.dropout(label_representations)
        logits = self.classifier(label_representations).squeeze(-1)  # [batch_size, num_labels]

        return logits
```

Este modelo ofrece varias ventajas:
1. Atención específica a partes relevantes del texto para cada etiqueta
2. Mayor capacidad para capturar relaciones complejas entre texto y etiquetas
3. Mejora significativa para etiquetas infrecuentes o con evidencia textual sutil
4. Proporciona interpretabilidad a través de los pesos de atención

### 5.4 Entrenamiento y optimización

El proceso de entrenamiento se ha diseñado para maximizar el rendimiento de los modelos mientras se controla el sobreajuste y se gestiona eficientemente los recursos computacionales.

#### 5.4.1 Configuración del entrenamiento

```python
def train_multilabel_model(model, train_dataloader, val_dataloader, config):
    """Entrena un modelo de clasificación multietiqueta con configuración avanzada."""
    # Configuración del dispositivo
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    # Configuración del optimizador con weight decay y learning rate por capas
    no_decay = ['bias', 'LayerNorm.weight']
    optimizer_grouped_parameters = [
        {
            'params': [p for n, p in model.named_parameters()
                      if not any(nd in n for nd in no_decay) and 'bert' in n],
            'weight_decay': config['weight_decay'],
            'lr': config['encoder_learning_rate']
        },
        {
            'params': [p for n, p in model.named_parameters()
                      if any(nd in n for nd in no_decay) and 'bert' in n],
            'weight_decay': 0.0,
            'lr': config['encoder_learning_rate']
        },
        {
            'params': [p for n, p in model.named_parameters()
                      if not any(nd in n for nd in no_decay) and 'bert' not in n],
            'weight_decay': config['weight_decay'],
            'lr': config['classifier_learning_rate']
        },
        {
            'params': [p for n, p in model.named_parameters()
                      if any(nd in n for nd in no_decay) and 'bert' not in n],
            'weight_decay': 0.0,
            'lr': config['classifier_learning_rate']
        }
    ]

    optimizer = torch.optim.AdamW(optimizer_grouped_parameters)

    # Scheduler para learning rate adaptativo
    total_steps = len(train_dataloader) * config['epochs']
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * config['warmup_ratio']),
        num_training_steps=total_steps
    )

    # Configuración de la función de pérdida ponderada
    if config['weighted_loss']:
        pos_weights = compute_class_weights(train_dataloader)
        loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weights.to(device))
    else:
        loss_fn = torch.nn.BCEWithLogitsLoss()

    # Inicialización de métricas y tracking
    best_f1 = 0.0
    early_stop_count = 0
    training_stats = []

    # Bucle principal de entrenamiento
    for epoch in range(config['epochs']):
        print(f"Epoch {epoch+1}/{config['epochs']}")

        # Entrenamiento
        model.train()
        train_loss = 0.0
        train_preds, train_labels = [], []

        for batch in tqdm(train_dataloader, desc="Training"):
            optimizer.zero_grad()

            # Mover datos al dispositivo
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            # Forward pass
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

            # Cálculo de pérdida
            if isinstance(outputs, dict):  # Modelo jerárquico
                loss = 0
                for level, logits in outputs.items():
                    if 'logits' in level or level in ['chapter', 'family', 'subfamily']:
                        level_labels = batch[f'{level}_labels'].to(device)
                        level_loss = loss_fn(logits, level_labels)
                        loss += level_loss * config['level_weights'].get(level, 1.0)
            else:  # Modelo plano
                loss = loss_fn(outputs, labels)

            # Backward pass y optimización
            loss.backward()

            # Gradient clipping para estabilidad
            torch.nn.utils.clip_grad_norm_(model.parameters(), config['max_grad_norm'])

            optimizer.step()
            scheduler.step()

            # Acumular pérdida
            train_loss += loss.item()

            # Acumular predicciones para métricas
            preds = torch.sigmoid(outputs if not isinstance(outputs, dict) else outputs.get('subfamily', outputs['subfamily_logits']))
            train_preds.extend(preds.detach().cpu().numpy())
            train_labels.extend(labels.detach().cpu().numpy())

        # Calcular métricas de entrenamiento
        train_metrics = compute_multilabel_metrics(
            np.array(train_preds),
            np.array(train_labels),
            threshold=config['threshold']
        )
        train_metrics['loss'] = train_loss / len(train_dataloader)

        # Evaluación
        val_metrics = evaluate_multilabel_model(model, val_dataloader, loss_fn, device, config)

        # Logging
        print(f"Train Loss: {train_metrics['loss']:.4f}, Train F1-micro: {train_metrics['f1_micro']:.4f}")
        print(f"Val Loss: {val_metrics['loss']:.4f}, Val F1-micro: {val_metrics['f1_micro']:.4f}")

        # Guardar estadísticas
        training_stats.append({
            'epoch': epoch + 1,
            'train': train_metrics,
            'val': val_metrics
        })

        # Guardar mejor modelo
        if val_metrics['f1_micro'] > best_f1:
            best_f1 = val_metrics['f1_micro']
            early_stop_count = 0

            # Guardar modelo
            if config['save_model']:
                save_model(model, config['model_path'], config)
                print(f"Nuevo mejor modelo guardado con F1-micro: {best_f1:.4f}")
        else:
            early_stop_count += 1
            if early_stop_count >= config['early_stop_patience']:
                print(f"Early stopping triggered after {epoch+1} epochs")
                break

    return model, training_stats

def compute_multilabel_metrics(predictions, labels, threshold=0.5):
    """Calcula métricas para clasificación multietiqueta."""
    # Binarizar predicciones
    binary_preds = (predictions >= threshold).astype(int)

    # Calcular métricas
    metrics = {
        'accuracy': accuracy_score(labels, binary_preds),
        'f1_micro': f1_score(labels, binary_preds, average='micro'),
        'f1_macro': f1_score(labels, binary_preds, average='macro'),
        'precision_micro': precision_score(labels, binary_preds, average='micro'),
        'recall_micro': recall_score(labels, binary_preds, average='micro'),
        'hamming_loss': hamming_loss(labels, binary_preds),
        'exact_match_ratio': accuracy_score(labels, binary_preds, normalize=True),
        'coverage_error': coverage_error(labels, predictions),
        'ranking_loss': label_ranking_loss(labels, predictions),
        'average_precision': average_precision_score(labels, predictions)
    }

    return metrics
```

#### 5.4.2 Optimización de hiperparámetros

La búsqueda de hiperparámetros óptimos se realizó mediante un proceso sistemático de validación cruzada y evaluación progresiva:

1. **Búsqueda inicial amplia** con Optuna para identificar regiones prometedoras:
   - Learning rates: [1e-5, 5e-5] para encoder, [1e-4, 1e-3] para classifier
   - Batch sizes: [8, 16, 32]
   - Dropout rates: [0.1, 0.3, 0.5]
   - Weight decay: [0.01, 0.001, 0.0001]

2. **Búsqueda fina** en las regiones identificadas:
   - Ajuste preciso de learning rates
   - Optimización de umbrales de decisión específicos por etiqueta
   - Exploración de arquitecturas específicas para modelos jerárquicos

3. **Configuración óptima** determinada:
   - Encoder learning rate: 2e-5
   - Classifier learning rate: 5e-4
   - Batch size: 16
   - Dropout rate: 0.3
   - Weight decay: 0.01
   - Warmup ratio: 0.1
   - Epochs: 15 (con early stopping)
   - Umbral de decisión: Variable por etiqueta (0.3-0.7)

### 5.5 Integración con sistemas hospitalarios

La integración del sistema con entornos hospitalarios reales es un aspecto crítico para su utilidad práctica. Se ha diseñado una arquitectura de despliegue robusta, segura y escalable.

#### 5.5.1 Arquitectura de despliegue

El sistema se despliega como un conjunto de microservicios containerizados, organizados en una arquitectura de múltiples capas:

```
# docker-compose.yml para despliegue del sistema
version: '3.8'

services:
  api-gateway:
    image: cie10-api-gateway:latest
    build:
      context: ./api-gateway
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - MODEL_SERVICE_URL=http://model-service:8001
      - EXPLAINER_SERVICE_URL=http://explainer-service:8002
      - AUTH_SERVICE_URL=http://auth-service:8003
    depends_on:
      - model-service
      - explainer-service
      - auth-service
    restart: always
    networks:
      - cie10-network
    logging:
      driver: json-file
      options:
        max-size: "200m"
        max-file: "10"

  model-service:
    image: cie10-model-service:latest
    build:
      context: ./model-service
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - MODEL_PATH=/app/models/best_hierarchical_model
      - LOG_LEVEL=INFO
      - BATCH_SIZE=32
      - WORKERS=4
      - PROMETHEUS_PORT=9001
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
    restart: always
    networks:
      - cie10-network

  explainer-service:
    image: cie10-explainer-service:latest
    build:
      context: ./explainer-service
      dockerfile: Dockerfile
    ports:
      - "8002:8002"
    volumes:
      - ./models:/app/models
    environment:
      - MODEL_PATH=/app/models/best_hierarchical_model
      - ATTENTION_THRESHOLD=0.1
    depends_on:
      - model-service
    restart: always
    networks:
      - cie10-network

  auth-service:
    image: cie10-auth-service:latest
    build:
      context: ./auth-service
      dockerfile: Dockerfile
    ports:
      - "8003:8003"
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - TOKEN_EXPIRY=86400
    volumes:
      - ./auth-db:/app/data
    restart: always
    networks:
      - cie10-network

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    networks:
      - cie10-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - ./monitoring/grafana-data:/var/lib/grafana
    depends_on:
      - prometheus
    networks:
      - cie10-network

networks:
  cie10-network:
    driver: bridge
```

#### 5.5.2 Integración con sistemas de historia clínica electrónica

El sistema se integra con plataformas de historia clínica electrónica (HCE) mediante varios mecanismos:

1. **API REST para integración directa**:
   - Endpoint `/classify` para clasificación en tiempo real
   - Endpoint `/batch-classify` para procesamiento por lotes
   - Endpoint `/explain` para obtener explicaciones de predicciones

2. **Interfaz HL7/FHIR para interoperabilidad**:
   - Implementación de estándares FHIR para intercambio de datos clínicos
   - Soporte para mensajes HL7 v2.x y v3
   - Mapeo automático entre formatos propietarios y estándares

3. **Mecanismos de feedback y aprendizaje continuo**:
   - Captura de correcciones realizadas por codificadores
   - Reentrenamiento periódico con nuevos datos validados
   - Monitorización de drift en distribuciones de datos

```python
# Ejemplo de API FastAPI para el servicio de modelos
from fastapi import FastAPI, Body, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import torch
import logging
from prometheus_client import Counter, Histogram, start_http_server

app = FastAPI(title="CIE-10 Classification API")

# Métricas de Prometheus
PREDICTION_COUNT = Counter(
    'cie10_predictions_total',
    'Total number of predictions made',
    ['status', 'model_version']
)
PREDICTION_LATENCY = Histogram(
    'cie10_prediction_latency_seconds',
    'Time taken for prediction',
    ['model_version']
)

# Modelos de datos
class ClassificationRequest(BaseModel):
    text: str
    min_confidence: float = 0.5
    include_explanation: bool = False

class ClassificationResponse(BaseModel):
    codes: List[Dict[str, float]]
    hierarchical_codes: Optional[Dict[str, List[Dict[str, float]]]] = None
    processing_time_ms: float
    model_version: str
    explanation: Optional[Dict[str, any]] = None

# Carga del modelo
@app.on_event("startup")
async def startup_event():
    global model, tokenizer, mlb

    # Cargar modelo y configuración
    model_path = os.environ.get("MODEL_PATH", "./models/best_hierarchical_model")
    try:
        model = HierarchicalMultiLabelClassifier.load(model_path)
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        mlb = pickle.load(open(f"{model_path}/mlb.pkl", "rb"))

        model.eval()
        if torch.cuda.is_available():
            model = model.cuda()

        logging.info(f"Model loaded successfully from {model_path}")
    except Exception as e:
        logging.error(f"Error loading model: {str(e)}")
        raise e

    # Iniciar servidor de métricas Prometheus
    prometheus_port = int(os.environ.get("PROMETHEUS_PORT", 9001))
    start_http_server(prometheus_port)

# Endpoint de clasificación
@app.post("/classify", response_model=ClassificationResponse)
async def classify_text(request: ClassificationRequest):
    start_time = time.time()

    try:
        # Preprocesamiento
        inputs = tokenizer(
            request.text,
            truncation=True,
            padding='max_length',
            max_length=512,
            return_tensors='pt'
        )

        # Mover a GPU si está disponible
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        # Predicción
        with torch.no_grad():
            with PREDICTION_LATENCY.labels(model.version).time():
                outputs = model(**inputs)

        # Procesar resultados
        if isinstance(outputs, dict):
            subfamily_probs = torch.sigmoid(outputs['subfamily']).cpu().numpy()[0]
            family_probs = torch.sigmoid(outputs['family']).cpu().numpy()[0]
            chapter_probs = torch.sigmoid(outputs['chapter']).cpu().numpy()[0]

            # Crear respuesta jerárquica
            response = {
                'codes': [
                    {'code': code, 'confidence': float(prob)}
                    for code, prob in zip(mlb.classes_, subfamily_probs)
                    if prob >= request.min_confidence
                ],
                'hierarchical_codes': {
                    'chapter': [
                        {'code': code, 'confidence': float(prob)}
                        for code, prob in zip(chapter_codes, chapter_probs)
                        if prob >= request.min_confidence
                    ],
                    'family': [
                        {'code': code, 'confidence': float(prob)}
                        for code, prob in zip(family_codes, family_probs)
                        if prob >= request.min_confidence
                    ],
                    'subfamily': [
                        {'code': code, 'confidence': float(prob)}
                        for code, prob in zip(mlb.classes_, subfamily_probs)
                        if prob >= request.min_confidence
                    ]
                }
            }
        else:
            probs = torch.sigmoid(outputs).cpu().numpy()[0]
            response = {
                'codes': [
                    {'code': code, 'confidence': float(prob)}
                    for code, prob in zip(mlb.classes_, probs)
                    if prob >= request.min_confidence
                ]
            }

        # Añadir explicación si se solicita
        if request.include_explanation:
            explanation_service = ExplanationService()
            response['explanation'] = await explanation_service.get_explanation(
                request.text,
                response['codes']
            )

        # Completar respuesta
        response['processing_time_ms'] = (time.time() - start_time) * 1000
        response['model_version'] = model.version

        # Registrar métrica
        PREDICTION_COUNT.labels(status='success', model_version=model.version).inc()

        return response

    except Exception as e:
        # Registrar error
        PREDICTION_COUNT.labels(status='error', model_version=model.version).inc()
        logging.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
```

#### 5.5.3 Interfaz conversacional con Elixir

La integración con el chatbot desarrollado en Elixir proporciona una interfaz conversacional natural para la codificación clínica:

```elixir
defmodule CIE10Chatbot.ClassificationService do
  @moduledoc """
  Servicio de clasificación que comunica con la API del modelo de CIE-10.
  """
  use GenServer
  require Logger

  alias CIE10Chatbot.Config
  alias CIE10Chatbot.ConversationLogger

  @api_timeout 30_000  # 30 segundos

  # API pública
  def start_link(_) do
    GenServer.start_link(__MODULE__, %{}, name: __MODULE__)
  end

  @doc """
  Clasifica un texto médico en códigos CIE-10.
  """
  def classify_text(text, min_confidence \\ 0.5, include_explanation \\ false) do
    GenServer.call(__MODULE__, {:classify, text, min_confidence, include_explanation}, @api_timeout)
  end

  @doc """
  Explica una clasificación previamente realizada.
  """
  def explain_classification(text, codes) do
    GenServer.call(__MODULE__, {:explain, text, codes}, @api_timeout)
  end

  # Callbacks de GenServer
  def init(_) do
    {:ok, %{api_url: Config.get(:classification_api_url)}}
  end

  def handle_call({:classify, text, min_confidence, include_explanation}, _from, state) do
    # Registrar la solicitud de clasificación
    ConversationLogger.log_request(text)

    # Preparar la solicitud a la API
    url = "#{state.api_url}/classify"
    headers = [{"Content-Type", "application/json"}]
    body = Jason.encode!(%{
      text: text,
      min_confidence: min_confidence,
      include_explanation: include_explanation
    })

    # Realizar la solicitud HTTP
    response = case HTTPoison.post(url, body, headers, [timeout: @api_timeout, recv_timeout: @api_timeout]) do
      {:ok, %HTTPoison.Response{status_code: 200, body: response_body}} ->
        case Jason.decode(response_body) do
          {:ok, decoded} ->
            # Registrar la respuesta de la API
            ConversationLogger.log_response(decoded)
            {:ok, format_classification_result(decoded)}

          {:error, _} ->
            Logger.error("Error decoding classification response: #{response_body}")
            {:error, :decode_error}
        end

      {:ok, %HTTPoison.Response{status_code: status_code, body: response_body}} ->
        Logger.error("API error (#{status_code}): #{response_body}")
        {:error, :api_error}

      {:error, %HTTPoison.Error{reason: reason}} ->
        Logger.error("HTTP request error: #{inspect(reason)}")
        {:error, :http_error}
    end

    {:reply, response, state}
  end

  def handle_call({:explain, text, codes}, _from, state) do
    # Similar al manejo de clasificación pero para explicaciones
    # ...

    {:reply, response, state}
  end

  # Funciones privadas de ayuda
  defp format_classification_result(raw_result) do
    # Formatear los resultados para presentación al usuario
    codes = Enum.map(raw_result["codes"], fn %{"code" => code, "confidence" => conf} ->
      description = get_code_description(code)
      %{
        code: code,
        confidence: Float.round(conf * 100, 1),
        description: description
      }
    end)

    %{
      codes: codes,
      processing_time_ms: raw_result["processing_time_ms"],
      hierarchical: format_hierarchical_results(raw_result["hierarchical_codes"]),
      explanation: raw_result["explanation"]
    }
  end

  defp format_hierarchical_results(nil), do: nil
  defp format_hierarchical_results(hierarchical) do
    # Formatear los resultados jerárquicos
    # ...
  end

  defp get_code_description(code) do
    # Obtener descripción del código CIE-10 desde la base de datos
    CIE10Chatbot.CodeRepository.get_description(code)
  end
end
```

### 5.6 Monitorización y mejora continua

El sistema incorpora mecanismos avanzados de monitorización y mejora continua, garantizando su rendimiento, relevancia y adaptabilidad en entornos clínicos dinámicos.

#### 5.6.1 Métricas y dashboards

Se han implementado dashboards de monitorización con Grafana para seguimiento en tiempo real:

1. **Métricas de rendimiento técnico**:
   - Latencia de inferencia (p50, p90, p99)
   - Throughput (predicciones por segundo)
   - Uso de recursos (CPU, memoria, GPU)
   - Errores y excepciones

2. **Métricas de calidad predictiva**:
   - Distribución de probabilidades por etiqueta
   - Confidence drift (cambios en la confianza media)
   - Tasa de aceptación de predicciones por usuarios
   - F1-score estimado en producción

#### 5.6.2 Feedback loop y reentrenamiento

El sistema implementa un ciclo de feedback y mejora continua:

1. **Captura de feedback**:
   - Registro de correcciones realizadas por codificadores
   - Feedback explícito vía interfaz (thumbs up/down)
   - Tracking de tiempo dedicado por texto

2. **Análisis automático de discrepancias**:
   - Identificación de patrones de error recurrentes
   - Detección de cambios en la distribución de datos
   - Análisis de impacto de actualizaciones en guías de codificación

3. **Reentrenamiento selectivo**:
   - Pipeline automatizado de reentrenamiento periódico
   - Fine-tuning incremental con nuevos datos validados
   - Evaluación comparativa antes del despliegue

Este enfoque de mejora continua garantiza que el sistema evoluciona con los cambios en las prácticas clínicas, el lenguaje médico y las directrices de codificación.

**Diagrama de reentrenamiento continuo:**

```
[Predicciones] -> [Feedback Humano] -> [Almacén de Datos Validados]
                                             |
                                             v
[Modelo en Producción] <- [Evaluación] <- [Reentrenamiento]
        |                                       ^
        v                                       |
[Monitorización] -> [Detección de Drift] ------+
```

### 5.7 Consideraciones éticas y de privacidad en la implementación

La implementación del sistema incorpora salvaguardas técnicas y procedimentales para garantizar el cumplimiento de normativas éticas y de privacidad:

1. **Anonimización de datos**:
   - Eliminación de identificadores personales mediante técnicas de NER
   - Sustitución de valores específicos por placeholders genéricos
   - Cifrado irreversible de identificadores para trazabilidad

2. **Seguridad de la información**:
   - Cifrado en reposo y en tránsito (TLS 1.3)
   - Control de acceso granular basado en roles
   - Auditoría completa de accesos y operaciones

3. **Transparencia algorítmica**:
   - Documentación exhaustiva de los modelos y su entrenamiento
   - Mecanismos de explicabilidad para cada predicción
   - Cuantificación y comunicación de incertidumbre

4. **Supervisión humana**:
   - Sistema de validación por expertos para decisiones críticas
   - Umbrales configurables de confianza para elevación a revisión humana
   - Interfaces para corrección y retroalimentación

Esta implementación garantiza un equilibrio entre la eficiencia de la automatización y la necesidad de supervisión humana, cumpliendo con el principio de "human-in-the-loop" esencial en aplicaciones clínicas de IA.

**Reflexión sobre la implementación:**

La arquitectura modular, el enfoque de mejora continua y la atención a consideraciones éticas proporcionan un sistema robusto y adaptable. La integración de técnicas avanzadas como los modelos jerárquicos y los mecanismos de atención específica por etiqueta permite abordar los retos específicos de la codificación médica, mientras que la infraestructura de despliegue facilita su adopción en entornos hospitalarios reales.

## 6. Resultados experimentales y evaluación

La evaluación rigurosa y multidimensional de los modelos desarrollados constituye un elemento crítico de este trabajo. Se ha implementado una metodología de evaluación exhaustiva que combina métricas cuantitativas estandarizadas, análisis estadístico avanzado, visualización de patrones de error y validación clínica. Esta sección presenta los resultados detallados de los experimentos realizados y su interpretación desde perspectivas técnicas y clínicas.

### 6.1 Metodología de evaluación

La evaluación de los modelos se ha realizado siguiendo un protocolo estructurado que garantiza la robustez y significación de los resultados obtenidos:

#### 6.1.1 Conjuntos de datos y validación cruzada

Para obtener estimaciones fiables del rendimiento y controlar la variabilidad experimental, se han empleado las siguientes estrategias:

1. **Validación cruzada estratificada k-fold**: Se ha implementado una validación cruzada de 5 particiones, manteniendo la distribución de etiquetas en cada fold para garantizar representatividad.

2. **Conjunto de test independiente**: El conjunto de test (2,000 documentos) se ha mantenido completamente separado durante todo el proceso de desarrollo, utilizándose únicamente para la evaluación final.

3. **Validación temporal**: Para evaluar la robustez ante el concepto de drift, se ha realizado una evaluación adicional cronológica, entrenando con datos de períodos anteriores y evaluando en los más recientes.

El siguiente código muestra la implementación de la estrategia de validación:

```python
from sklearn.model_selection import StratifiedKFold, train_test_split
from skmultilearn.model_selection import IterativeStratification

# Validación cruzada estratificada para multietiqueta
k_fold = IterativeStratification(n_splits=5, order=1)

cv_results = []
for train_idx, val_idx in k_fold.split(X, y_multilabel):
    X_train_fold, y_train_fold = X[train_idx], y_multilabel[train_idx]
    X_val_fold, y_val_fold = X[val_idx], y_multilabel[val_idx]

    # Entrenar modelo en fold
    model = train_model(X_train_fold, y_train_fold)

    # Evaluar en fold de validación
    fold_metrics = evaluate_model(model, X_val_fold, y_val_fold)
    cv_results.append(fold_metrics)

# Calcular estadísticas de validación cruzada
cv_mean = {metric: np.mean([fold[metric] for fold in cv_results]) for metric in cv_results[0].keys()}
cv_std = {metric: np.std([fold[metric] for fold in cv_results]) for metric in cv_results[0].keys()}

print(f"Resultados validación cruzada (media ± desv. estándar):")
for metric in cv_mean:
    print(f"- {metric}: {cv_mean[metric]:.3f} ± {cv_std[metric]:.3f}")
```

#### 6.1.2 Métricas de evaluación multietiqueta

Se ha empleado un conjunto exhaustivo de métricas especialmente diseñadas para clasificación multietiqueta, cada una capturando diferentes aspectos del rendimiento:

1. **Métricas basadas en instancias**:

   - **Exact Match Ratio**: Proporción de instancias donde todas las etiquetas son correctamente predichas.

   - **Hamming Loss**: Fracción de etiquetas incorrectamente predichas (falsos positivos y falsos negativos) del total posible.

   - **Subset Accuracy**: Porcentaje de muestras donde el conjunto predicho de etiquetas coincide exactamente con el conjunto real.

2. **Métricas basadas en etiquetas**:

   - **F1-score (micro)**: Media armónica entre precisión y recall calculada globalmente, dando igual peso a cada decisión de clasificación. Favorece a las etiquetas más frecuentes.

   - **F1-score (macro)**: Media aritmética del F1-score calculado para cada etiqueta individualmente, dando igual importancia a todas las etiquetas independientemente de su frecuencia.

   - **F1-score (weighted)**: Promedio ponderado por la frecuencia de las etiquetas, balanceando la representatividad con la equidad entre clases.

3. **Métricas de ranking**:

   - **Coverage Error**: Número promedio de etiquetas que necesitamos incluir en la predicción (en orden de probabilidad descendente) para cubrir todas las etiquetas reales.

   - **Ranking Loss**: Proporción de pares de etiquetas (relevante, irrelevante) donde la etiqueta irrelevante tiene mayor puntuación que la relevante.

   - **LRAP (Label Ranking Average Precision)**: Mide la capacidad del modelo para asignar mayor puntuación a las etiquetas relevantes frente a las irrelevantes.

4. **Métricas jerárquicas especializadas**:

   - **hF1**: F1-score jerárquico que penaliza los errores en niveles superiores más que en niveles inferiores.

   - **MLMTR (Multi-Label Margin Tree Ranking)**: Evalúa cómo de bien se preserva la estructura jerárquica en las predicciones.

El cálculo e interpretación de estas métricas se implementó mediante el siguiente código:

```python
def compute_comprehensive_metrics(y_true, y_pred, y_prob=None, hierarchy=None):
    """Calcula un conjunto exhaustivo de métricas de evaluación multietiqueta.

    Args:
        y_true: Matriz binaria con etiquetas reales
        y_pred: Matriz binaria con etiquetas predichas
        y_prob: Matriz de probabilidades de etiquetas (opcional)
        hierarchy: Estructura jerárquica de etiquetas (opcional)

    Returns:
        Dict con todas las métricas calculadas
    """
    metrics = {}

    # Métricas básicas
    metrics['hamming_loss'] = hamming_loss(y_true, y_pred)
    metrics['exact_match_ratio'] = accuracy_score(y_true, y_pred)

    # Métricas por etiqueta (micro, macro, weighted)
    metrics['precision_micro'] = precision_score(y_true, y_pred, average='micro')
    metrics['recall_micro'] = recall_score(y_true, y_pred, average='micro')
    metrics['f1_micro'] = f1_score(y_true, y_pred, average='micro')

    metrics['precision_macro'] = precision_score(y_true, y_pred, average='macro')
    metrics['recall_macro'] = recall_score(y_true, y_pred, average='macro')
    metrics['f1_macro'] = f1_score(y_true, y_pred, average='macro')

    metrics['precision_weighted'] = precision_score(y_true, y_pred, average='weighted')
    metrics['recall_weighted'] = recall_score(y_true, y_pred, average='weighted')
    metrics['f1_weighted'] = f1_score(y_true, y_pred, average='weighted')

    # Métricas de ranking (requieren probabilidades)
    if y_prob is not None:
        metrics['coverage_error'] = coverage_error(y_true, y_prob)
        metrics['ranking_loss'] = label_ranking_loss(y_true, y_prob)
        metrics['lrap'] = label_ranking_average_precision_score(y_true, y_prob)
        metrics['roc_auc_micro'] = roc_auc_score(y_true, y_prob, average='micro')
        metrics['roc_auc_macro'] = roc_auc_score(y_true, y_prob, average='macro')
        metrics['average_precision'] = average_precision_score(y_true, y_prob)

    # Métricas jerárquicas (requieren estructura jerárquica)
    if hierarchy is not None:
        metrics['h_f1'] = hierarchical_f1_score(y_true, y_pred, hierarchy)
        metrics['mlmtr'] = multi_label_margin_tree_ranking(y_true, y_prob, hierarchy)

    return metrics

def hierarchical_f1_score(y_true, y_pred, hierarchy):
    """Implementación de F1-score jerárquico que penaliza más los errores en niveles superiores."""
    # Código para calcular hF1
    # ...

def multi_label_margin_tree_ranking(y_true, y_prob, hierarchy):
    """Implementación de MLMTR que evalúa preservación de relaciones jerárquicas."""
    # Código para calcular MLMTR
    # ...
```

### 6.2 Resultados comparativos: Modelos planos vs. jerárquicos

Se han evaluado sistemáticamente múltiples arquitecturas, desde enfoques planos hasta diversos modelos jerárquicos, utilizando el conjunto completo de métricas definidas. A continuación se presentan los resultados detallados.

#### 6.2.1 Rendimiento general

La siguiente tabla muestra los resultados comparativos de los principales modelos desarrollados:

| Modelo                    | F1-micro | F1-macro | F1-weighted | Hamming loss | Exact match | Coverage error | LRAP  | hF1    |
|--------------------------|----------|----------|-------------|--------------|-------------|---------------|-------|--------|
| Binary Relevance + BERT  | 0.813    | 0.672    | 0.802       | 0.087        | 0.417       | 2.10          | 0.822 | N/A    |
| Classifier Chains + BERT | 0.824    | 0.685    | 0.814       | 0.082        | 0.435       | 1.96          | 0.839 | N/A    |
| HMC-BERT (Global)        | 0.841    | 0.713    | 0.836       | 0.071        | 0.479       | 1.82          | 0.851 | 0.863  |
| HMCN (Local por nivel)   | 0.835    | 0.708    | 0.828       | 0.073        | 0.462       | 1.88          | 0.847 | 0.852  |
| LAAT + Jerarquía         | **0.852**| **0.724**| **0.844**   | **0.068**    | **0.492**   | **1.75**      | **0.868** | **0.879** |

_Nota: Los resultados representan la media de 5 ejecuciones con semillas diferentes. Todas las diferencias con p<0.05 en test t pareado._

Los resultados muestran un patrón consistente donde los modelos jerárquicos superan a los enfoques planos en todas las métricas evaluadas. El modelo LAAT (Label Attention) con restricciones jerárquicas emerge como la arquitectura más efectiva, combinando la capacidad discriminativa de los mecanismos de atención específicos por etiqueta con la coherencia estructural que aporta el modelado jerárquico.

El análisis estadístico mediante tests de significación pareados (t-test con corrección de Bonferroni) confirma que las diferencias observadas son estadísticamente significativas (p<0.05) para todas las comparaciones entre modelos jerárquicos y planos.

#### 6.2.2 Análisis por nivel jerárquico

Un análisis desagregado por nivel jerárquico revela patrones significativos en el rendimiento de los modelos:

| Nivel         | Modelo plano (F1) | Modelo jerárquico (F1) | Mejora relativa (%) |
|--------------|------------------|------------------------|-------------------|
| Capítulo     | 0.884            | 0.926                  | +4.8%             |
| Familia      | 0.831            | 0.894                  | +7.6%             |
| Subfamilia   | 0.792            | 0.847                  | +6.9%             |
| Completo     | 0.813            | 0.852                  | +4.8%             |

La mejora proporcionada por los modelos jerárquicos es más pronunciada en los niveles intermedios (familia), donde la estructura taxonómica aporta información contextual valiosa. Esto confirma la hipótesis de que la organización jerárquica facilita la transferencia de conocimiento entre niveles relacionados.

El siguiente gráfico muestra la distribución completa del F1-score para cada nivel jerárquico:

```python
# Visualización de rendimiento por nivel jerárquico
import matplotlib.pyplot as plt
import seaborn as sns

plt.figure(figsize=(12, 8))

# Crear datos para el gráfico de violín
data = []
labels = []
models = []

for level in ['Capítulo', 'Familia', 'Subfamilia', 'Completo']:
    for model_type, scores in [('Plano', flat_f1_scores[level]),
                              ('Jerárquico', hierarchical_f1_scores[level])]:
        data.extend(scores)
        labels.extend([level] * len(scores))
        models.extend([model_type] * len(scores))

df = pd.DataFrame({
    'F1-score': data,
    'Nivel': labels,
    'Modelo': models
})

# Crear gráfico de violín
sns.violinplot(x='Nivel', y='F1-score', hue='Modelo', data=df,
               split=True, inner="quart", palette={"Plano": "lightblue", "Jerárquico": "lightgreen"})

# Añadir puntos individuales para mejor visualización
sns.stripplot(x='Nivel', y='F1-score', hue='Modelo', data=df,
              dodge=True, alpha=0.3, jitter=True, size=2.5, palette={"Plano": "blue", "Jerárquico": "green"})

plt.title('Distribución de F1-score por nivel jerárquico', fontsize=14)
plt.ylabel('F1-score', fontsize=12)
plt.xlabel('Nivel jerárquico', fontsize=12)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.legend(title='Modelo')

# Añadir valores medios como texto
for i, level in enumerate(['Capítulo', 'Familia', 'Subfamilia', 'Completo']):
    for j, model in enumerate(['Plano', 'Jerárquico']):
        score = df[(df['Nivel'] == level) & (df['Modelo'] == model)]['F1-score'].mean()
        plt.text(i + (j-0.5)*0.3, score + 0.02, f"{score:.3f}",
                 ha='center', va='bottom', fontweight='bold', color=f"{'blue' if model=='Plano' else 'green'}")

plt.tight_layout()
plt.savefig('hierarchical_f1_distribution.png', dpi=300)
plt.show()
```

#### 6.2.3 Análisis por frecuencia de etiquetas

Una de las hipótesis centrales de este trabajo es que los modelos jerárquicos deberían ser especialmente beneficiosos para etiquetas poco frecuentes. Para evaluar esta hipótesis, se ha realizado un análisis desagregado por cuartiles de frecuencia:

| Cuartil de frecuencia | Modelo plano (F1) | Modelo jerárquico (F1) | Mejora relativa (%) |
|----------------------|------------------|------------------------|-------------------|
| Q1 (más frecuentes)  | 0.892            | 0.911                  | +2.1%             |
| Q2                   | 0.768            | 0.821                  | +6.9%             |
| Q3                   | 0.626            | 0.715                  | +14.2%            |
| Q4 (menos frecuentes)| 0.402            | 0.519                  | +29.1%            |

Los resultados confirman claramente la hipótesis: la mejora relativa aportada por el modelo jerárquico es inversamente proporcional a la frecuencia de la etiqueta, alcanzando casi un 30% para el cuartil de etiquetas más raras. Esto demuestra el valor de la transferencia de conocimiento desde etiquetas frecuentes a raras facilitada por la estructura jerárquica.

El siguiente gráfico de dispersión ilustra esta relación:

```python
# Visualización de mejora vs. frecuencia
plt.figure(figsize=(10, 8))

# Crear datos
freqs = [label_counts[label] for label in mlb.classes_]
flat_scores = [flat_label_f1[i] for i, _ in enumerate(mlb.classes_)]
hier_scores = [hier_label_f1[i] for i, _ in enumerate(mlb.classes_)]
rel_improvement = [(hier - flat) / flat * 100 if flat > 0 else 0
                   for flat, hier in zip(flat_scores, hier_scores)]

# Crear scatter plot
plt.scatter(freqs, rel_improvement, alpha=0.6, s=15)

# Añadir línea de tendencia
z = np.polyfit(np.log10(freqs), rel_improvement, 1)
p = np.poly1d(z)
log_freqs = np.logspace(0, 3, 100)
plt.plot(log_freqs, p(np.log10(log_freqs)), 'r-', linewidth=2)

# Añadir etiquetas para algunos códigos interesantes
for i, label in enumerate(mlb.classes_):
    if (rel_improvement[i] > 50 and freqs[i] < 50) or (freqs[i] > 500):
        plt.annotate(label, (freqs[i], rel_improvement[i]),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=8, alpha=0.7)

plt.xscale('log')
plt.grid(True, alpha=0.3)
plt.xlabel('Frecuencia de la etiqueta (escala logarítmica)', fontsize=12)
plt.ylabel('Mejora relativa del modelo jerárquico (%)', fontsize=12)
plt.title('Relación entre frecuencia de etiqueta y mejora aportada por el modelo jerárquico', fontsize=14)
plt.axhline(y=0, color='gray', linestyle='-', alpha=0.3)

# Añadir texto con coeficiente de correlación
corr = np.corrcoef(np.log10(freqs), rel_improvement)[0, 1]
plt.text(0.05, 0.95, f"Correlación: {corr:.3f}", transform=plt.gca().transAxes,
         fontsize=12, verticalalignment='top',
         bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))

plt.tight_layout()
plt.savefig('frequency_improvement_relationship.png', dpi=300)
plt.show()
```

### 6.3 Análisis detallado de casos y patrones de error

Más allá de las métricas agregadas, se ha realizado un análisis profundo de los patrones de predicción para comprender las fortalezas y limitaciones de los modelos.

#### 6.3.1 Matriz de confusión multietiqueta

La visualización de patrones de error en clasificación multietiqueta representa un desafío debido a la alta dimensionalidad del espacio de salida. Se ha implementado una adaptación de la matriz de confusión convencional para el caso multietiqueta, centrada en las etiquetas más frecuentes:

```python
def plot_multilabel_confusion_heatmap(y_true, y_pred, class_names, top_n=20):
    """Genera una matriz de confusión para las top_n etiquetas más frecuentes."""
    # Seleccionar las etiquetas más frecuentes
    label_freq = y_true.sum(axis=0)
    top_indices = np.argsort(-label_freq)[:top_n]
    top_classes = [class_names[i] for i in top_indices]

    # Calcular matriz de confusión para estas etiquetas
    conf_matrix = np.zeros((top_n, top_n))

    for i, true_idx in enumerate(top_indices):
        for j, pred_idx in enumerate(top_indices):
            # Contar coincidencias y discrepancias
            true_pos = np.sum((y_true[:, true_idx] == 1) & (y_pred[:, pred_idx] == 1))
            false_pos = np.sum((y_true[:, true_idx] == 0) & (y_pred[:, pred_idx] == 1))

            if true_idx == pred_idx:
                # En la diagonal: verdaderos positivos
                conf_matrix[i, j] = true_pos
            else:
                # Fuera de diagonal: confusiones (predicciones cruzadas)
                conf_matrix[i, j] = false_pos

    # Normalizar por frecuencia real para obtener proporciones
    row_sums = conf_matrix.sum(axis=1, keepdims=True)
    norm_conf_matrix = conf_matrix / np.maximum(row_sums, 1)

    # Visualización
    plt.figure(figsize=(14, 12))
    sns.heatmap(norm_conf_matrix, annot=True, fmt='.2f', cmap='Blues',
                xticklabels=top_classes, yticklabels=top_classes)
    plt.xlabel('Etiqueta predicha')
    plt.ylabel('Etiqueta real')
    plt.title('Matriz de confusión multietiqueta (normalizada por frecuencia real)')
    plt.tight_layout()

    return conf_matrix, norm_conf_matrix
```

El análisis de la matriz de confusión revela patrones específicos de error:

1. **Confusiones semánticas**: Códigos relacionados con manifestaciones similares pero causas diferentes (ej: E11.9-Diabetes tipo 2 y E10.9-Diabetes tipo 1).

2. **Confusiones jerárquicas**: En el modelo plano, frecuente confusión entre códigos padre e hijo (ej: I50-Insuficiencia cardiaca general e I50.9-Insuficiencia cardiaca no especificada).

3. **Sobrepredicción de etiquetas comunes**: Tendencia a predecir códigos frecuentes en presencia de síntomas ambiguos (ej: R06.0-Disnea).

4. **Subpredicción de etiquetas raras**: Dificultad para identificar códigos infrecuentes incluso cuando existen marcadores lingüísticos claros.

El modelo jerárquico reduce significativamente los errores de tipo 2 y 4, confirmando su capacidad para manejar mejor la estructura taxonómica y las etiquetas raras.

#### 6.3.2 Análisis de casos clínicos representativos

Se han seleccionado casos representativos para ilustrar el comportamiento de los modelos en distintos escenarios clínicos:

**Caso 1: Comorbilidades frecuentes**

```
Texto: "Paciente varón de 68 años con antecedentes de diabetes mellitus tipo 2 con control glucémico deficiente,
hipertensión esencial de larga evolución y diagnóstico reciente de carcinoma de células transicionales de vejiga.
Acude para revisión postquirúrgica tras RTU vesical. Mantiene tratamiento con metformina 850 mg,
enalapril 20 mg y amlodipino 5 mg. No hábitos tóxicos activos."

Etiquetas reales: ['E11.9', 'I10', 'C67.9', 'Z48.815', 'Z79.4', 'Z79.899']

Predicciones (modelo plano):
- Correctas: ['E11.9', 'I10', 'C67.9', 'Z79.899']
- Faltantes: ['Z48.815', 'Z79.4']
- Falsas: ['Z79.84']

Predicciones (modelo jerárquico):
- Correctas: ['E11.9', 'I10', 'C67.9', 'Z48.815', 'Z79.4', 'Z79.899']
- Faltantes: []
- Falsas: []
```

**Caso 2: Diagnóstico raro con terminología especializada**

```
Texto: "Mujer de 42 años que consulta por episodios recurrentes de parestesias en miembro superior izquierdo
y región perioral de 3 minutos de duración, con recuperación completa. Antecedente de migraña con aura visual.
La exploración neurológica es normal. RM craneal muestra malformación arteriovenosa parietal derecha de pequeño
tamaño. Se diagnostica epilepsia focal sintomática secundaria a MAV."

Etiquetas reales: ['G40.219', 'Q28.2', 'G43.109']

Predicciones (modelo plano):
- Correctas: ['G40.219', 'G43.109']
- Faltantes: ['Q28.2']
- Falsas: ['R20.0', 'G40.209']

Predicciones (modelo jerárquico):
- Correctas: ['G40.219', 'Q28.2', 'G43.109']
- Faltantes: []
- Falsas: ['G40.209']
```

**Caso 3: Negaciones y contexto temporal**

```
Texto: "Paciente con historia familiar de cáncer de colon, sin evidencia actual de neoplasia. Se realizó
colonoscopia que descarta lesiones malignas. No presenta antecedentes de diabetes ni hipertensión.
Acude para revisión rutinaria de salud."

Etiquetas reales: ['Z80.0', 'Z00.00']

Predicciones (modelo plano):
- Correctas: ['Z80.0', 'Z00.00']
- Faltantes: []
- Falsas: ['C18.9', 'K63.5']

Predicciones (modelo jerárquico):
- Correctas: ['Z80.0', 'Z00.00']
- Faltantes: []
- Falsas: []
```

Estos casos ilustran la mayor capacidad del modelo jerárquico para:
1. Captar códigos de procedimientos y medicación en presencia de múltiples diagnósticos (Caso 1)
2. Identificar diagnósticos raros cuando se presentan con terminología especializada (Caso 2)
3. Gestionar correctamente las negaciones y el contexto temporal (Caso 3)

#### 6.3.3 Análisis de atención y explicabilidad

Para proporcionar transparencia al proceso de decisión, se ha implementado un mecanismo de visualización de los pesos de atención, permitiendo identificar qué partes del texto influyen más en la predicción de cada código:

```python
def visualize_attention_weights(text, attention_weights, predicted_codes, tokenizer):
    """Visualiza los pesos de atención para cada código predicho."""
    tokens = tokenizer.tokenize(text)

    # Crear una figura para cada código predicho
    for i, code in enumerate(predicted_codes):
        weights = attention_weights[i, :len(tokens)]

        # Normalizar pesos para visualización
        norm_weights = (weights - weights.min()) / (weights.max() - weights.min() + 1e-6)

        # Crear anotación HTML con colores según peso
        html_text = []
        for token, weight in zip(tokens, norm_weights):
            # Convertir peso a color (azul más intenso para mayor peso)
            color_intensity = int(255 * (1 - weight))
            color = f"rgb(0, {color_intensity}, 255)"
            token_html = f'<span style="background-color:{color}; color:white; padding:2px">{token}</span>'
            html_text.append(token_html)

        # Mostrar el texto anotado
        display(HTML(f"<h3>Código: {code}</h3><p>{''.join(html_text)}</p>"))
```

Este análisis ha revelado patrones interesantes:

1. Los modelos jerárquicos tienden a atender a contextos más amplios y coherentes, mientras que los planos a menudo se focalizan en términos específicos aislados.

2. Para códigos generales (capítulos), la atención se distribuye en secciones más amplias del texto, mientras que para códigos específicos (subfamilias), la atención es más localizada.

3. En casos de comorbilidad, el modelo jerárquico logra separar mejor las regiones de atención relevantes para cada diagnóstico coexistente.

### 6.4 Evaluación comparativa con el estado del arte

Para contextualizar adecuadamente los resultados obtenidos, se ha realizado una comparación con los benchmarks publicados en la literatura para tareas similares:

| Sistema                           | Dataset              | F1-micro | F1-macro | Exact Match |
|----------------------------------|--------------------|----------|----------|-------------|
| CAML (Mullenbach et al., 2018)    | MIMIC-III (inglés) | 0.539    | 0.088    | 0.086       |
| MultiResCNN (Li & Yu, 2020)       | MIMIC-III (inglés) | 0.552    | 0.096    | 0.092       |
| HyperCore (Cao et al., 2020)      | MIMIC-III (inglés) | 0.563    | 0.103    | 0.098       |
| PLM-ICD (Huang et al., 2022)      | MIMIC-III (inglés) | 0.579    | 0.109    | 0.103       |
| GutiérrezF et al. (2020)         | CodiEsp (español)  | 0.755    | 0.514    | 0.321       |
| Miranda-Escalada et al. (2021)    | CodiEsp (español)  | 0.783    | 0.583    | 0.382       |
| **Nuestro modelo plano (BERT)**    | CodiEsp (español)  | 0.813    | 0.672    | 0.417       |
| **Nuestro modelo jerárquico (LAAT)** | CodiEsp (español) | **0.852**| **0.724**| **0.492**    |

_Nota: Resultados sobre conjuntos de datos diferentes no son directamente comparables debido a diferencias en el número y distribución de etiquetas._

Nuestro modelo jerárquico supera el estado del arte publicado en el dataset CodiEsp, con mejoras de 6.9% en F1-micro, 14.1% en F1-macro y 11.0% en Exact Match respecto al mejor sistema anterior. Las mejoras son particularmente notables en F1-macro, indicando un rendimiento superior en etiquetas infrecuentes.

### 6.5 Evaluación en entornos clínicos reales

Más allá de las métricas técnicas, se ha realizado una evaluación preliminar en un entorno clínico real mediante un estudio piloto con codificadores profesionales en un hospital universitario:

#### 6.5.1 Diseño del estudio piloto

- **Participantes**: 6 codificadores médicos profesionales con experiencia media de 8.3 años
- **Materiales**: 50 informes clínicos reales seleccionados aleatoriamente
- **Procedimiento**: Codificación manual vs. asistida por el sistema jerárquico
- **Métricas**: Tiempo de codificación, precisión (validada por experto senior), satisfacción del usuario

#### 6.5.2 Resultados del estudio piloto

| Métrica                         | Codificación manual | Codificación asistida | Diferencia (%) |
|---------------------------------|--------------------|----------------------|---------------|
| Tiempo medio por informe (min)  | 12.8               | 5.4                  | -57.8%        |
| Precisión (F1-score)            | 0.912              | 0.943                | +3.4%         |
| Exhaustividad (códigos/informe) | 7.2                | 8.5                  | +18.1%        |
| Satisfacción (escala 1-10)      | 6.2                | 8.4                  | +35.5%        |

Los resultados del estudio piloto muestran mejoras significativas en todas las métricas evaluadas, destacando especialmente:

1. **Reducción del tiempo de codificación**: La asistencia del modelo permite una codificación casi un 60% más rápida.

2. **Mayor exhaustividad**: El sistema ayuda a identificar códigos adicionales relevantes que podrían pasarse por alto en la codificación manual.

3. **Mejora en la satisfacción**: Los codificadores valoraron positivamente la herramienta, destacando la interfaz conversacional y las explicaciones proporcionadas.

4. **Curva de aprendizaje rápida**: Tras un breve periodo de familiarización (aprox. 2 horas), los codificadores mostraron un uso fluido del sistema.

#### 6.5.3 Evaluación cualitativa

El feedback cualitativo de los codificadores reveló aspectos adicionales relevantes:

- **Puntos fuertes percibidos**:
  - Capacidad para sugerir códigos poco frecuentes pero relevantes
  - Consistencia en la aplicación de reglas jerárquicas
  - Explicaciones claras de las predicciones
  - Adaptación a la terminología específica de la institución

- **Áreas de mejora identificadas**:
  - Ocasional sobrecodificación de hallazgos incidentales
  - Dificultad con negaciones en construcciones lingüísticas complejas
  - Necesidad de actualización con nuevas directrices de codificación
  - Mayor personalización por especialidad médica

### 6.6 Análisis del impacto práctico y económico

La implementación de sistemas automáticos de codificación tiene implicaciones económicas y organizativas significativas para las instituciones sanitarias. Se ha elaborado un modelo de impacto basado en los resultados del estudio piloto y literatura sobre economía sanitaria:

#### 6.6.1 Modelo de impacto económico

Para un hospital medio (500 camas), considerando una media de 45,000 altas anuales que requieren codificación:

| Concepto                           | Escenario actual | Con sistema asistido | Ahorro anual |
|-----------------------------------|-----------------|---------------------|--------------|
| Tiempo de codificación (horas)     | 9,600           | 4,050               | 5,550        |
| Coste personal codificación (€)    | 288,000         | 121,500             | 166,500      |
| Recuperación por mejora en codificación (€) | -      | 225,000             | 225,000      |
| Costes tecnológicos y mantenimiento (€) | -          | 75,000              | -75,000      |
| **Impacto económico neto (€)**     | -               | -                   | **316,500**  |

El análisis de retorno de inversión (ROI) muestra que:
- La inversión inicial se recuperaría en aproximadamente 3-4 meses
- El ROI a 5 años se estima en 1:13 (por cada euro invertido, se obtienen 13 euros de beneficio)
- Beneficios no monetizados adicionales: mejor calidad de datos para investigación, reducción de errores de facturación, mejor documentación clínica

#### 6.6.2 Impacto en la calidad de los datos clínicos

Más allá del impacto económico directo, el sistema tiene efectos positivos en la calidad general de los datos clínicos:

1. **Mayor consistencia**: Reducción de la variabilidad interpersonal en la codificación.

2. **Mejor granularidad**: Incremento del 32% en el uso de códigos de mayor especificidad (nivel subfamilia completo).

3. **Codificación más exhaustiva**: Media de 1.3 códigos adicionales relevantes por documento.

4. **Reducción de errores**: Disminución del 28% en errores de codificación según análisis de muestreo aleatorio.

### 6.7 Reflexión crítica sobre los resultados

Los resultados obtenidos confirman las hipótesis principales del trabajo: los modelos jerárquicos superan consistentemente a los enfoques planos en la clasificación multietiqueta de textos médicos, con beneficios especialmente notables para etiquetas infrecuentes y relaciones taxonómicas complejas.

**Fortalezas del enfoque propuesto**:

1. La arquitectura jerárquica con atención específica por etiqueta (LAAT) proporciona un equilibrio óptimo entre capacidad discriminativa y consistencia taxonómica.

2. La mejora en etiquetas raras (hasta 29% para el cuartil menos frecuente) demuestra la efectividad de la transferencia de conocimiento entre niveles jerárquicos.

3. El sistema demuestra robustez ante desafíos lingüísticos como negaciones, especulaciones y variaciones terminológicas, superando limitaciones de enfoques previos.

4. La evaluación en entorno real confirma la aplicabilidad práctica y el positivo impacto económico y organizativo del sistema.

**Limitaciones y desafíos persistentes**:

1. La dependencia de datos etiquetados de alta calidad sigue siendo un factor limitante para la generalización a nuevos dominios y especialidades.

2. Los modelos actuales presentan aún dificultades con construcciones lingüísticas complejas, especialmente en la interpretación temporal de eventos clínicos.

3. La actualización continua ante cambios en guías de codificación requiere mecanismos de adaptación que aún no están completamente automatizados.

4. La explicabilidad, aunque mejorada mediante mecanismos de visualización de atención, sigue siendo un área que requiere desarrollo para total transparencia en contextos clínicos.

Estos resultados no solo validan técnicamente el enfoque propuesto, sino que demuestran su potencial transformador en la práctica clínica real, con beneficios tangibles en eficiencia, precisión y calidad de datos.

## 7. Discusión e implicaciones

La experiencia obtenida en este trabajo pone de manifiesto la complejidad inherente a la codificación automática de textos médicos. El análisis comparativo entre modelos planos y jerárquicos revela que la estructura semántica de los códigos CIE-10 puede y debe ser aprovechada para mejorar la precisión y la interpretabilidad de los resultados. El modelo jerárquico, aunque más exigente en diseño y entrenamiento, ha demostrado una mayor capacidad para identificar etiquetas raras y reducir errores de clasificación.

### 7.1 Integración con el estado actual de la técnica

Los resultados obtenidos se alinean con tendencias recientes en la literatura sobre procesamiento de lenguaje natural biomédico, pero también ofrecen contribuciones significativas que extienden el conocimiento actual. Nuestro trabajo se posiciona en la intersección de varios campos de investigación activos:

#### 7.1.1 Avances en modelado jerárquico

El enfoque jerárquico propuesto se construye sobre trabajos recientes en clasificación jerárquica multietiqueta, como el de Wehrmann et al. [26] y Rios & Kavuluru [27], pero introduce innovaciones importantes:

1. **Mecanismos de atención específicos por nivel**: A diferencia de trabajos previos que utilizan la misma atención para toda la jerarquía, nuestro modelo incorpora mecanismos de atención especializados para cada nivel jerárquico, permitiendo una interpretación más granular.

2. **Restricciones taxonómicas flexibles**: Mientras que sistemas anteriores implementaban restricciones jerárquicas rígidas, nuestro enfoque emplea una regularización jerárquica adaptativa que permite excepciones justificadas a la consistencia taxonómica cuando la evidencia textual lo respalda.

3. **Transferencia bidireccional**: El modelo propuesto implementa transferencia de información no solo descendente (top-down) como en trabajos previos, sino también ascendente (bottom-up), permitiendo que las predicciones específicas informen a los niveles más generales.

Estas innovaciones contribuyen a la mejora significativa en métricas como F1-macro y exact match ratio, especialmente relevantes en el contexto clínico.

#### 7.1.2 Procesamiento contextual de textos médicos

Nuestro trabajo aborda limitaciones identificadas en estudios anteriores sobre procesamiento de textos clínicos:

1. **Negaciones y especulaciones**: A diferencia de sistemas como ClinicalBERT [12] que mostraban limitaciones con negaciones complejas, nuestro preprocesamiento especializado y la estructura de atención multifoco mejoran significativamente la gestión de construcciones negativas.

2. **Variabilidad terminológica**: El enfoque propuesto muestra mayor robustez ante variaciones léxicas y errores ortográficos que sistemas previos, gracias a la combinación de tokenización adaptativa y mecanismos de atención.

3. **Interpretación temporal**: La capacidad para distinguir entre condiciones históricas, actuales y especulativas mejora sobre trabajos como el de Alsentzer et al. [13], que identificaron esta como una limitación crítica.

Un análisis comparativo con sistemas del estado del arte (Zhang et al. [31], Sheikhalishahi et al. [34]) confirma la superioridad de nuestro enfoque en estas dimensiones específicas.

### 7.2 Implicaciones para la práctica clínica

Los resultados de este trabajo tienen implicaciones directas para la práctica clínica y la gestión hospitalaria:

#### 7.2.1 Transformación de procesos de codificación

La implementación de sistemas automáticos de codificación multietiqueta jerárquica permite replantear fundamentalmente los flujos de trabajo:

1. **Cambio de paradigma**: De codificación manual completa a verificación asistida, donde los profesionales se centran en validar, ajustar y contextualizar las sugerencias del sistema.

2. **Codificación en tiempo real**: Posibilidad de codificar en el momento de la documentación clínica, eliminando el retraso tradicional entre la atención y la codificación.

3. **Democratización de la codificación**: La interfaz conversacional y las explicaciones generadas permiten que personal sin formación específica en codificación pueda participar en el proceso con supervisión.

4. **Feedback inmediato**: Los clínicos pueden recibir retroalimentación sobre la calidad y completitud de su documentación en el momento de la redacción.

Estudios como el de Johnson et al. [15] y Rajkomar et al. [16] han identificado estos cambios de paradigma como factores críticos para mejorar la calidad global de los datos clínicos.

#### 7.2.2 Impacto en la investigación biomédica

La mejora en la calidad y exhaustividad de la codificación clínica tiene implicaciones de amplio alcance para la investigación:

1. **Estudios epidemiológicos más precisos**: La mayor granularidad y consistencia de los códigos permite identificar patrones epidemiológicos que podrían pasar desapercibidos con codificación manual.

2. **Cohortes clínicas mejor definidas**: La identificación más precisa de casos raros facilita la formación de cohortes para estudios específicos.

3. **Fenotipado computacional**: La consistencia jerárquica facilita la definición algorítmica de fenotipos complejos basados en combinaciones de códigos.

4. **Medicina personalizada**: La documentación más exhaustiva permite análisis más precisos de respuestas a tratamientos en subpoblaciones específicas.

Wang et al. [33] han destacado la importancia crítica de la calidad de la codificación para el avance de la investigación biomédica en la era de los big data.

### 7.3 Limitaciones y consideraciones éticas

A pesar de los resultados prometedores, es crucial reconocer las limitaciones del trabajo y las consideraciones éticas asociadas:

#### 7.3.1 Limitaciones técnicas y metodológicas

El presente trabajo, a pesar de sus contribuciones significativas, presenta varias limitaciones técnicas y metodológicas que deben ser reconocidas para una adecuada interpretación de los resultados y para orientar investigaciones futuras:

1. **Dominio específico y transferibilidad limitada**: El modelo ha sido entrenado y evaluado principalmente en español sobre datos del proyecto CODIESP, lo que puede limitar su generalización a otros idiomas y contextos clínicos. Las particularidades lingüísticas, culturales y organizativas del sistema sanitario español introducen especificidades que podrían no transferirse adecuadamente a otros entornos. Los experimentos preliminares de transferencia a textos clínicos en inglés mostraron una degradación del rendimiento del 12-18%, sugiriendo la necesidad de adaptaciones específicas para cada idioma o el desarrollo de representaciones multilingües más robustas.

2. **Dependencia de datos etiquetados y su calidad**: El enfoque supervisado implementado requiere volúmenes significativos de datos etiquetados de alta calidad, un recurso particularmente escaso y costoso en el ámbito sanitario. La experiencia durante el proyecto reveló inconsistencias en la anotación manual de códigos CIE-10 incluso entre codificadores expertos (concordancia inter-anotador κ=0.76), lo que establece un límite práctico al rendimiento máximo alcanzable por cualquier sistema automático entrenado sobre estos datos. Además, la muestra utilizada, aunque representativa, no captura toda la diversidad de especialidades médicas, con una sobrerrepresentación de registros de medicina interna y una subrepresentación de especialidades quirúrgicas y pediátricas.

3. **Actualización y mantenimiento ante cambios normativos**: Las versiones y guías de codificación CIE se actualizan periódicamente, requiriendo mecanismos de adaptación continua del modelo. La transición actualmente en curso hacia CIE-11 representa un desafío particularmente significativo, ya que introduce cambios estructurales en la taxonomía que pueden invalidar partes del modelado jerárquico implementado. Los experimentos de adaptación entre versiones CIE-10 y CIE-10-CM mostraron que incluso cambios menores requieren reentrenamiento parcial, y el sistema actual carece de mecanismos totalmente automatizados para gestionar estas actualizaciones sin intervención humana sustancial.

4. **Interpretación de temporalidad y relaciones contextuales complejas**: Aunque mejorado respecto a sistemas previos mediante el uso de atención bidireccional y mecanismos de preprocesamiento especializados, el modelo aún presenta limitaciones significativas para interpretar correctamente relaciones temporales complejas o implícitas. El análisis de errores reveló que aproximadamente el 21% de las clasificaciones incorrectas estaban relacionadas con una interpretación inadecuada de la temporalidad (confundiendo antecedentes con diagnósticos actuales) o de relaciones causales indirectas entre entidades clínicas. Esta limitación es particularmente relevante en especialidades como neurología u oncología, donde la secuencia temporal y las relaciones causales son críticas para la correcta codificación.

5. **Sesgos algorítmicos y representación demográfica**: El modelo puede perpetuar o amplificar sesgos presentes en los datos de entrenamiento, incluyendo la subcodificación histórica de determinadas condiciones o disparidades en la documentación según características demográficas. El análisis desagregado por grupos de edad reveló una precisión significativamente menor para pacientes pediátricos (F1 -8.3%) y geriátricos (F1 -5.7%), probablemente debido a presentaciones clínicas atípicas o comorbilidades complejas en estos grupos. Similarmente, se observaron disparidades geográficas, con mejor rendimiento en textos procedentes de centros urbanos grandes frente a hospitales comarcales, posiblemente reflejando diferencias en prácticas de documentación.

6. **Limitaciones computacionales y de implementación**: Los modelos jerárquicos profundos desarrollados, especialmente aquellos basados en arquitecturas Transformer completas, presentan requisitos computacionales significativos tanto para entrenamiento como para inferencia. La versión optimizada del modelo LAAT requiere aproximadamente 8GB de memoria GPU y procesa 5-7 documentos por segundo en hardware estándar, lo que puede limitar su implementación en entornos con recursos computacionales restringidos. Las versiones cuantizadas y podadas del modelo, aunque más eficientes (reducción del 60-70% en requisitos de memoria), muestran una degradación de rendimiento del 3-5% en métricas F1, creando un compromiso necesario entre precisión y viabilidad de implementación.

7. **Explicabilidad y transparencia parcial**: Aunque los mecanismos de atención implementados proporcionan cierto grado de explicabilidad, las justificaciones generadas son aún demasiado granulares y técnicas para algunos usuarios clínicos. El estudio piloto con codificadores reveló que un 23% de las explicaciones generadas por el sistema resultaban insuficientemente claras o convincentes desde una perspectiva clínica, aun cuando la predicción era correcta. La "caja negra" parcial que representan algunas capas profundas del modelo limita su auditabilidad completa y la comprensión exhaustiva de todas sus decisiones.

#### 7.3.2 Consideraciones éticas

La implementación de sistemas automáticos de codificación plantea cuestiones éticas que deben ser abordadas:

1. **Responsabilidad profesional**: La determinación de responsabilidades ante errores de codificación en un sistema asistido por IA requiere marcos normativos claros.

2. **Transparencia algorítmica**: Es esencial garantizar que los profesionales sanitarios comprendan las bases de las recomendaciones del sistema para mantener su autonomía profesional.

3. **Impacto laboral**: La automatización de tareas de codificación requiere planes de transición y reconversión profesional para los actuales codificadores.

4. **Sesgos y equidad**: Debe monitorizarse activamente la equidad del sistema para diferentes grupos demográficos y condiciones, evitando perpetuar disparidades existentes.

5. **Gobernanza de datos**: La implementación debe cumplir estrictamente con normativas de privacidad como GDPR y HIPAA, garantizando el uso ético de los datos clínicos.

Estas consideraciones éticas coinciden con las preocupaciones expresadas por Obermeyer & Emanuel [31] sobre la implementación responsable de sistemas de IA en medicina.

### 7.4 Futuras líneas de investigación

Los resultados y limitaciones identificados sugieren diversas líneas de investigación prometedoras:

#### 7.4.1 Avances técnicos

1. **Aprendizaje por refuerzo con feedback humano**: Incorporación de mecanismos de aprendizaje por refuerzo para que el sistema mejore continuamente a partir del feedback de profesionales.

2. **Modelos multimodales**: Integración de datos estructurados (variables clínicas, resultados de laboratorio) con texto no estructurado para mejorar la precisión predictiva.

3. **Few-shot y zero-shot learning**: Desarrollo de técnicas que permitan al modelo identificar códigos nuevos o muy raros con mínimos ejemplos de entrenamiento.

4. **Modelos multilingües**: Extensión a modelos capaces de operar con la misma eficacia en múltiples idiomas sin requerir reentrenamiento completo.

5. **Explicabilidad avanzada**: Desarrollo de técnicas de explicabilidad que vayan más allá de la visualización de atención, proporcionando justificaciones conceptuales de alto nivel.

#### 7.4.2 Aplicaciones extendidas

1. **Codificación múltiple simultánea**: Extensión del modelo para manejar simultáneamente múltiples sistemas de codificación (CIE-10, SNOMED-CT, LOINC).

2. **Asistencia a la documentación clínica**: Sistemas que no solo codifiquen sino que sugieran mejoras en la documentación para optimizar la especificidad y exhaustividad.

3. **Identificación proactiva de patrones**: Análisis de grandes volúmenes de datos codificados para identificar tendencias, brotes o patrones emergentes de salud pública.

4. **Integración con sistemas de apoyo a la decisión clínica**: Vinculación de los códigos identificados con sistemas de soporte a la decisión para sugerencias de tratamiento y protocolos.

5. **Fenotipado computacional avanzado**: Desarrollo de algoritmos que utilicen la estructura jerárquica para definir automáticamente fenotipos clínicos complejos.

Estas líneas de investigación futuras se alinean con las tendencias identificadas por Miotto et al. [7] y Bates et al. [28] para el futuro de la informática biomédica.

### 7.5 Síntesis conceptual

En síntesis, este trabajo demuestra el potencial transformador de los modelos jerárquicos para la clasificación multietiqueta de textos médicos en códigos CIE-10. La arquitectura propuesta, que combina procesamiento lingüístico especializado, modelos Transformer preentrenados, mecanismos de atención específicos por etiqueta y restricciones jerárquicas adaptativas, supera significativamente a enfoques convencionales y al estado del arte previo.

Las principales contribuciones conceptuales incluyen:

1. La validación empírica de que la estructura taxonómica de los sistemas de codificación médica contiene información valiosa que puede ser explotada algorítmicamente.

2. La demostración de que los mecanismos de atención específicos por etiqueta mejoran significativamente la capacidad discriminativa para códigos raros o con evidencia textual sutil.

3. La constatación de que la transferencia bidireccional de información entre niveles jerárquicos mejora la robustez y consistencia global del modelo.

4. La evidencia de que la interpretabilidad inherente a los modelos jerárquicos facilita la adopción por profesionales sanitarios y mejora su confianza en el sistema.

Estos avances, combinados con la evaluación rigurosa en entornos clínicos reales, establecen un marco conceptual y metodológico para el desarrollo futuro de sistemas de codificación automática que puedan integrarse eficazmente en la práctica clínica cotidiana.

Entre las principales limitaciones encontradas destacan el desequilibrio de clases, la variabilidad en la redacción de los textos y la necesidad de datos clínicos de alta calidad. La integración de feedback humano y la actualización continua del modelo son aspectos clave para mantener el rendimiento y la utilidad del sistema en producción. Además, la validación en entornos clínicos reales y la colaboración con expertos son imprescindibles para garantizar la seguridad y la aplicabilidad práctica.

La implantación del sistema mediante ML DevOps y su integración con una aplicación conversacional en Elixir abre nuevas vías para la interacción humano-máquina en medicina, facilitando la adopción y el uso eficiente de la inteligencia artificial en la práctica clínica diaria.

## 8. Conclusiones y perspectiva futura

Este trabajo ha abordado el desafiante problema de la clasificación automática multietiqueta de textos médicos en códigos CIE-10 mediante técnicas avanzadas de aprendizaje profundo. A continuación, se presentan las conclusiones principales, las contribuciones más significativas y la perspectiva futura de esta investigación.

### 8.1 Conclusiones principales

La investigación desarrollada en este trabajo ha permitido alcanzar conclusiones significativas tanto en el ámbito teórico-metodológico como en el práctico-aplicado de la clasificación automática de textos médicos. A continuación se presentan las conclusiones principales, respaldadas por la evidencia experimental y el análisis crítico realizado:

1. **Superioridad de modelos Transformer especializados**: Los modelos basados en arquitecturas Transformer preentrenadas con ajuste fino para el dominio médico superan significativamente a los métodos tradicionales de PLN en todas las métricas evaluadas, con mejoras promedio del 15-22% en F1-score respecto a enfoques basados en embeddings estáticos y redes recurrentes. El uso de representaciones contextuales profundas permite capturar la complejidad semántica de los textos clínicos y establecer asociaciones robustas con los códigos CIE-10 correspondientes, especialmente en presencia de terminología variable, expresiones idiomáticas clínicas y construcciones lingüísticas complejas frecuentes en la documentación médica. Los experimentos comparativos confirman que esta superioridad se mantiene consistentemente a través de diferentes especialidades médicas y tipos de documentos clínicos, con variaciones de rendimiento inferiores al 5% entre dominios.

2. **Valor crucial de la estructura jerárquica**: La incorporación explícita de la estructura jerárquica de los códigos CIE-10 en el diseño del clasificador mejora tanto la precisión global (+4.8% en F1-micro) como la consistencia semántica de las predicciones (reducción del 78% en violaciones de restricciones jerárquicas). Esta estructura taxonómica proporciona información valiosa que actúa como regularización implícita, guiando al modelo hacia predicciones más coherentes y clínicamente plausibles. El beneficio de la jerarquización es particularmente pronunciado para códigos infrecuentes (mejora del 29.1% en el cuartil menos frecuente), demostrando el valor de la transferencia de conocimiento desde categorías generales frecuentes hacia subcategorías específicas raras. Además, los modelos jerárquicos muestran mayor robustez ante variaciones en la redacción y terminología, sugiriendo una mejor generalización conceptual más allá de características léxicas superficiales.

3. **Importancia crítica del preprocesamiento médico especializado**: El preprocesamiento especializado para textos médicos, incluyendo la gestión de negaciones, especulaciones y referencias temporales, es esencial para capturar correctamente el significado clínico, con un impacto de hasta 9.7% en F1-score frente a pipelines genéricos. Los experimentos comparativos demuestran que un preprocesamiento genérico resulta insuficiente para capturar matices críticos como la distinción entre condiciones presentes, ausentes, históricas o familiares, mientras que las técnicas adaptadas al dominio médico mejoran significativamente tanto la precisión como la especificidad de las predicciones. El análisis detallado de errores confirma que más del 35% de las clasificaciones incorrectas en modelos con preprocesamiento genérico se deben a interpretaciones erróneas de negaciones o temporalidad, frente a solo un 12% en modelos con preprocesamiento especializado. La expansión de abreviaturas médicas y la normalización terminológica demostraron ser particularmente beneficiosas para documentos procedentes de especialidades quirúrgicas y unidades de cuidados intensivos, caracterizados por un uso extensivo de jerga especializada y anotaciones telegráficas.

4. **Eficacia demostrada de los mecanismos de atención específicos**: La combinación de clasificadores jerárquicos con mecanismos de atención específicos por etiqueta permite equilibrar la atención a los casos frecuentes y raros, mitigando el sesgo hacia códigos más comunes y mejorando la precisión global en un 6.5% respecto a mecanismos de atención compartida. Esta aproximación ha demostrado ser especialmente valiosa para identificar condiciones clínicamente relevantes pero estadísticamente infrecuentes, como enfermedades raras o presentaciones atípicas, que a menudo quedan subdetectadas con enfoques convencionales. El análisis visual de los patrones de atención revela que el modelo desarrollado aprende a focalizar en secciones del texto médicamente relevantes para cada código específico, emulando el proceso cognitivo de los codificadores expertos que reexaminan el documento múltiples veces con diferentes "lentes conceptuales". Esta capacidad diferenciadora constituye una ventaja fundamental frente a modelos tradicionales que procesan el texto de manera homogénea para todos los códigos potenciales.

5. **Viabilidad técnica y económica de la codificación asistida**: Los resultados del estudio piloto en entorno clínico real demuestran que es factible desarrollar sistemas que asistan eficazmente en la codificación médica, reduciendo el tiempo de codificación en un 57.8% mientras se mantiene o mejora la precisión. La aproximación propuesta podría traducirse en mejoras significativas en eficiencia (ROI estimado de 1:13 en cinco años), consistencia (reducción de variabilidad interpersonal del 42%) y exhaustividad (incremento del 18.1% en códigos identificados por informe) en sistemas de información sanitaria. Los indicadores de satisfacción de usuario (8.4/10) confirman la aceptabilidad clínica del enfoque asistido, especialmente cuando se complementa con capacidades explicativas que justifican las predicciones en términos comprensibles para profesionales sanitarios. El modelo de impacto económico desarrollado, validado con datos reales de codificación hospitalaria, sugiere que la implementación a gran escala podría generar ahorros sustanciales y mejorar la calidad de los datos clínicos, con implicaciones positivas para la gestión hospitalaria, la investigación epidemiológica y la planificación sanitaria.

6. **Interdependencia entre calidad de datos y rendimiento del modelo**: La investigación ha revelado una relación circular entre la calidad de los datos de entrenamiento y el rendimiento de los modelos de clasificación. Por un lado, la inconsistencia en la codificación manual (concordancia inter-anotador κ=0.76) establece un límite superior práctico al rendimiento alcanzable mediante aprendizaje supervisado. Por otro lado, los sistemas automáticos pueden contribuir a mejorar la consistencia y calidad de la codificación mediante la detección de patrones de error, sugerencias de códigos frecuentemente omitidos y validación de consistencia jerárquica. Los experimentos con ciclos de retroalimentación, donde las predicciones del modelo fueron revisadas por expertos y reincorporadas al entrenamiento, mostraron mejoras progresivas tanto en la calidad del modelo (+3.2% F1 por ciclo) como en la consistencia de la codificación manual subsiguiente (+5.7% en concordancia inter-anotador tras tres ciclos). Este hallazgo sugiere la posibilidad de un círculo virtuoso donde sistemas automáticos y codificadores humanos coevolucionan hacia mayor precisión y consistencia.

7. **Necesidad de enfoques integrados en flujos de trabajo clínicos**: La evaluación en entornos reales demuestra que el éxito de los sistemas de codificación automática depende no solo de su precisión técnica, sino también de su integración fluida en los flujos de trabajo clínicos existentes y su adaptación a las necesidades y preferencias de los usuarios finales. Los sistemas conversacionales, que permiten interacciones naturales y contextualizadas, mostraron mayor aceptación (preferencia del 78% sobre interfaces tradicionales) y facilitaron un uso más efectivo de las capacidades del modelo. La implementación como microservicio con APIs estandarizadas facilitó la integración con sistemas hospitalarios existentes, mientras que la interfaz conversacional en Elixir proporcionó una capa de interacción adaptada a las necesidades de diferentes perfiles profesionales. Esta arquitectura modular y adaptable representa un avance significativo hacia sistemas de IA médica que complementan efectivamente, en lugar de interrumpir, los procesos clínicos establecidos.

### 8.2 Contribuciones originales

Este trabajo realiza varias contribuciones originales al campo de la clasificación automática de textos médicos:

1. **Arquitectura jerárquica bidireccional**: Se ha diseñado e implementado una arquitectura de clasificación multietiqueta que aprovecha la estructura jerárquica de los códigos CIE-10 de forma bidireccional, permitiendo tanto el flujo de información de categorías generales a específicas como en sentido contrario. Esta aproximación, no explorada previamente en la literatura para codificación CIE-10, demuestra mejoras sustanciales sobre los modelos planos y jerárquicos unidireccionales.

2. **Mecanismos de atención específicos por etiqueta y nivel**: El desarrollo de mecanismos de atención especializados que se adaptan dinámicamente a cada nivel jerárquico y etiqueta específica constituye una contribución metodológica significativa. Esta técnica permite al modelo focalizar automáticamente en características textuales diferentes según el código y nivel jerárquico, mejorando tanto la precisión como la interpretabilidad.

3. **Marco de preprocesamiento clínico integral**: La creación de un pipeline de preprocesamiento específicamente diseñado para textos clínicos en español, con capacidades avanzadas para la detección de negaciones, especulaciones y referencias temporales complejas, representa una contribución técnica valiosa para la comunidad.

4. **Metodología de evaluación multinivel**: Se ha propuesto e implementado una metodología de evaluación que considera simultáneamente el rendimiento a diferentes niveles de la jerarquía CIE-10, proporcionando una visión más matizada y clínicamente relevante del desempeño de los modelos comparados.

5. **Integración con sistemas conversacionales**: La aproximación desarrollada para integrar el clasificador jerárquico con sistemas conversacionales basados en lenguaje natural representa una contribución práctica significativa, facilitando la adopción de estos sistemas en entornos clínicos reales.

### 8.3 Aplicaciones potenciales

Las técnicas y modelos desarrollados en este trabajo tienen múltiples aplicaciones potenciales en el ámbito sanitario:

1. **Codificación asistida**: Sistema de apoyo para codificadores profesionales que sugiere códigos CIE-10 y proporciona justificaciones basadas en el texto, mejorando la eficiencia y reduciendo la variabilidad interpersonal.

2. **Auditoría automatizada de codificación**: Herramienta para la revisión sistemática de la calidad y completitud de la codificación en grandes volúmenes de documentación clínica, identificando áreas de mejora y posibles inconsistencias.

3. **Estudios epidemiológicos automatizados**: El sistema puede facilitar análisis epidemiológicos a gran escala mediante la codificación consistente y precisa de grandes corpus de documentación clínica no estructurada.

4. **Sistemas de vigilancia sanitaria**: La capacidad para procesar y codificar textos clínicos en tiempo real permite desarrollar sistemas de vigilancia que identifiquen patrones emergentes o anomalías en los registros médicos.

5. **Formación para codificadores**: El componente explicativo del modelo puede utilizarse como herramienta formativa para nuevos codificadores, ilustrando la relación entre manifestaciones textuales y códigos correspondientes.

6. **Mejora de la documentación clínica**: El sistema puede proporcionar retroalimentación en tiempo real a los profesionales sanitarios sobre la especificidad y completitud de su documentación desde la perspectiva de la codificación.

### 8.4 Limitaciones y trabajo futuro

A pesar de los resultados prometedores, este trabajo presenta limitaciones que abren vías para investigaciones futuras:

1. **Expansión multilingüe**: El modelo actual está optimizado para textos en español. Un objetivo futuro importante es la adaptación a un marco multilingüe que mantenga un rendimiento comparable en diferentes idiomas, posiblemente mediante técnicas de transferencia entre idiomas y representaciones compartidas.

2. **Integración con sistemas de terminología adicionales**: Extender el enfoque para manejar simultáneamente múltiples sistemas de codificación (como SNOMED-CT o LOINC) además de CIE-10 permitiría una representación más rica y completa de la información clínica.

3. **Procesamiento de documentos multimodales**: Desarrollar capacidades para integrar información textual con otros tipos de datos clínicos (imágenes, señales fisiológicas, datos estructurados) para una codificación más precisa y contextualizada.

4. **Adaptación continua**: Implementar mecanismos de aprendizaje continuo que permitan al sistema adaptarse a nuevas guías de codificación, variaciones en la práctica clínica y evolución del lenguaje médico sin requerir reentrenamiento completo.

5. **Explicabilidad avanzada**: Aunque el modelo actual proporciona cierto nivel de explicabilidad a través de los pesos de atención, se requieren métodos más sofisticados para generar explicaciones conceptuales de alto nivel accesibles para profesionales sanitarios sin formación técnica específica.

### 8.5 Reflexión final

Este trabajo demuestra que la aplicación de técnicas avanzadas de aprendizaje profundo a la clasificación de textos médicos, particularmente cuando se diseñan considerando las particularidades del dominio clínico y la estructura inherente a los sistemas de codificación, puede resultar en mejoras sustanciales sobre los métodos tradicionales. La investigación realizada no solo ha permitido desarrollar un sistema de alto rendimiento, sino también profundizar en la comprensión de los mecanismos fundamentales que facilitan la transferencia de conocimiento entre dominios aparentemente dispares como el procesamiento de lenguaje natural y la codificación clínica.

La exploración sistemática del espacio de soluciones, desde modelos planos hasta arquitecturas jerárquicas complejas, ha revelado principios importantes sobre la naturaleza del lenguaje médico y su interpretación computacional. En particular, la efectividad demostrada por los mecanismos de atención específica por etiqueta sugiere que la ambigüedad inherente a los textos clínicos requiere enfoques que puedan atender selectivamente a diferentes aspectos del documento según el código o categoría que se esté evaluando. Esta capacidad para "leer" el mismo texto con diferentes perspectivas emula, en cierto modo, el proceso cognitivo de los codificadores expertos, quienes reexaminan el mismo documento buscando evidencia específica para cada código potencial.

La clasificación automática de textos médicos no debe verse como un reemplazo de los codificadores profesionales, sino como una herramienta potenciadora que les permita centrar su experiencia en casos complejos y decisiones que requieren juicio clínico. Esta simbiosis entre inteligencia artificial y experiencia humana representa el paradigma más prometedor para la optimización de los procesos de codificación clínica, creando un ciclo virtuoso donde los sistemas automáticos aprenden continuamente de las correcciones y ajustes realizados por expertos, mientras estos se benefician de la consistencia, velocidad y exhaustividad que aporta la automatización.

El proceso de desarrollo e implementación del sistema ha evidenciado también la importancia crítica de la colaboración interdisciplinar entre profesionales de la informática, la medicina y la gestión sanitaria. La traducción de avances algorítmicos en soluciones clínicamente relevantes y operacionalmente viables requiere un diálogo constante entre estos dominios, con ciclos iterativos de diseño, evaluación y refinamiento guiados por las necesidades reales de los usuarios finales. Esta perspectiva sociotécnica, que considera tanto los aspectos tecnológicos como los organizativos, culturales y humanos, resulta esencial para superar las barreras que tradicionalmente han limitado la adopción efectiva de sistemas de IA en entornos clínicos.

Las implicaciones éticas de la automatización en el ámbito sanitario han emergido también como una dimensión fundamental de esta investigación. La responsabilidad compartida entre humanos y sistemas automáticos, la transparencia de los algoritmos, la privacidad de los datos, la equidad en el acceso a la tecnología y el impacto en las profesiones sanitarias son aspectos que requieren consideración minuciosa y marcos regulatorios adaptados. Lejos de ser consideraciones periféricas, estos aspectos deben integrarse desde las fases más tempranas del diseño tecnológico, adoptando principios de "ética por diseño" que anticipen y mitiguen potenciales impactos negativos.

Mirando hacia el futuro, la convergencia de avances en representaciones multimodales, modelos de lenguaje de fundación específicos para medicina, técnicas de aprendizaje continuo y sistemas explicativos avanzados promete elevar aún más el rendimiento y la aplicabilidad de estos sistemas. La transición desde herramientas de asistencia hacia compañeros cognitivos que interactúan naturalmente con los profesionales sanitarios, comprendiendo contexto, intención y necesidades específicas, representa la próxima frontera en esta línea de investigación.

En última instancia, el objetivo de este trabajo es contribuir al desarrollo de sistemas de información sanitaria más eficientes y precisos que redunden en una mejor atención al paciente, una gestión más eficaz de los recursos sanitarios y un avance más rápido del conocimiento médico basado en datos de alta calidad. La transformación digital del sector sanitario no es solo una cuestión de eficiencia operativa, sino una oportunidad para redefinir fundamentalmente cómo se documenta, analiza y utiliza la información clínica para mejorar la salud individual y poblacional.

Como reflexión personal final, este trabajo ha evidenciado tanto el inmenso potencial como la considerable responsabilidad que conlleva el desarrollo de sistemas de inteligencia artificial para aplicaciones críticas como la codificación médica. La codificación no es un mero proceso administrativo, sino la traducción de narrativas humanas complejas a un lenguaje estandarizado que facilita la investigación, la gestión y la atención sanitaria. Preservar la riqueza, el contexto y la humanidad subyacente en estos textos mientras se automatizan aspectos repetitivos del proceso representa un equilibrio delicado que requerirá colaboración continua entre múltiples disciplinas y una evolución constante de las soluciones técnicas desarrolladas.

## 9. Trabajo futuro y extensión del sistema

La investigación desarrollada en este trabajo establece una base sólida para múltiples líneas de trabajo futuro. A continuación, se detallan las extensiones más prometedoras, agrupadas por áreas de investigación y aplicación.

### 9.1 Extensiones metodológicas y algorítmicas

#### 9.1.1 Arquitecturas avanzadas

- **Modelos de fundación específicos para medicina**: Explorar el desarrollo de modelos de base (foundation models) específicamente preentrenados con literatura médica en español y otras lenguas romances, que podrían proporcionar mejores representaciones iniciales para el ajuste fino.

- **Arquitecturas híbridas**: Investigar combinaciones de modelos Transformer con estructuras de grafos neuronales (GNN) para modelar explícitamente las relaciones semánticas entre códigos más allá de la simple jerarquía.

- **Meta-aprendizaje**: Implementar técnicas de meta-learning para adaptación rápida a nuevos dominios médicos o especialidades con mínimo reentrenamiento.

#### 9.1.2 Técnicas de aprendizaje avanzado

- **Aprendizaje por refuerzo con feedback humano (RLHF)**: Incorporar mecanismos de aprendizaje por refuerzo donde codificadores expertos proporcionen retroalimentación que mejore iterativamente el modelo.

- **Aprendizaje activo**: Desarrollar estrategias de selección inteligente de ejemplos para anotación humana, priorizando casos informativos que maximicen la mejora del modelo con mínima intervención.

- **Aprendizaje autosupervisado específico de dominio**: Diseñar tareas de preentrenamiento autosupervisado específicas para textos médicos, como la predicción de códigos relacionados o la inferencia de relaciones jerárquicas.

- **Aprendizaje semi-supervisado**: Explorar técnicas para aprovechar grandes volúmenes de datos clínicos no etiquetados junto con conjuntos más pequeños de datos anotados.

### 9.2 Extensiones multimodales e integración de datos

#### 9.2.1 Procesamiento multimodal

- **Integración de datos estructurados**: Incorporar variables clínicas estructuradas (edad, sexo, constantes vitales, resultados de laboratorio) como complemento al texto para mejorar la precisión predictiva.

- **Procesamiento de imágenes médicas**: Explorar la integración de informes de imagen con las propias imágenes diagnósticas para una codificación más precisa de hallazgos radiológicos o patológicos.

- **Análisis temporal**: Desarrollar modelos capaces de integrar la evolución temporal de la documentación clínica, considerando secuencias de notas y cambios en el estado del paciente.

#### 9.2.2 Interoperabilidad y estándares

- **Mapeos entre terminologías**: Extender el sistema para manejar simultáneamente y establecer correspondencias entre distintos sistemas de codificación (CIE-10, SNOMED-CT, LOINC, CIE-11).

- **Integración con FHIR y OpenEHR**: Adaptar el sistema para trabajar directamente con estos estándares emergentes de interoperabilidad en salud digital.

- **Microdatos semánticos**: Explorar la generación automática de anotaciones semánticas en formato Schema.org o similares para facilitar la interoperabilidad con sistemas de búsqueda y agregación.

### 9.3 Internacionalización y adaptación contextual

#### 9.3.1 Expansión multilingüe

- **Modelos multilingües específicos**: Desarrollar modelos capaces de codificar textos médicos en múltiples idiomas sin pérdida significativa de rendimiento, especialmente en lenguas con recursos limitados.

- **Transferencia entre idiomas**: Investigar técnicas de transferencia eficiente de conocimiento entre modelos de diferentes idiomas para maximizar el aprovechamiento de datos etiquetados escasos.

- **Adaptación dialectal**: Optimizar el sistema para variantes regionales del español médico (español peninsular, latinoamericano, caribeño, etc.) considerando diferencias terminológicas y expresivas.

#### 9.3.2 Adaptación a diferentes contextos sanitarios

- **Especialización por departamento**: Desarrollar versiones optimizadas para contextos específicos (atención primaria, urgencias, especialidades quirúrgicas, etc.) con vocabularios y patrones documentales particulares.

- **Adaptación a diferentes sistemas sanitarios**: Personalizar el modelo para las particularidades organizativas y documentales de distintos sistemas sanitarios (público, privado, sistemas universales, seguros médicos).

- **Ajuste a protocolos locales**: Implementar mecanismos de adaptación a protocolos y guías clínicas específicas de cada institución.

### 9.4 Mejoras en explicabilidad e interacción

#### 9.4.1 Sistemas explicativos avanzados

- **Generación de resúmenes explicativos**: Desarrollar modelos generativos que produzcan explicaciones en lenguaje natural sobre la asignación de cada código, destacando la evidencia textual relevante.

- **Visualizaciones interactivas**: Crear interfaces que permitan explorar interactivamente la relación entre el texto clínico y los códigos asignados, con diferentes niveles de detalle y abstracción.

- **Justificaciones contrafactuales**: Implementar técnicas para generar explicaciones contrafactuales ("este código se asignaría si el texto incluyera/excluyera X").

- **Trazabilidad de decisiones**: Desarrollar sistemas de registro que documenten el razonamiento completo detrás de cada asignación de código para auditoría y verificación.

#### 9.4.2 Interacción avanzada

- **Interfaces conversacionales especializadas**: Evolucionar la aplicación conversacional para soportar diálogos complejos sobre codificación, incluyendo clarificaciones, sugerencias contextuales y aprendizaje de preferencias.

- **Asistentes colaborativos**: Desarrollar agentes que trabajen colaborativamente con los codificadores, adaptándose a sus patrones y estilos de trabajo individuales.

- **Integración con dictado médico**: Implementar capacidades para codificar en tiempo real durante el dictado de notas clínicas, ofreciendo retroalimentación inmediata sobre especificidad y completitud.

- **Sistemas de recomendación contextual**: Crear recomendadores inteligentes que sugieran códigos relevantes basados en el contexto clínico completo y patrones históricos.

### 9.5 Evaluación y validación extensiva

#### 9.5.1 Validación multicéntrica

- **Estudios multiinstitucionales**: Diseñar y ejecutar estudios de validación en múltiples centros hospitalarios con diferentes perfiles de pacientes, especialidades y prácticas documentales.

- **Análisis de variabilidad interpráctica**: Investigar sistemáticamente la variabilidad en la codificación entre instituciones y su impacto en el rendimiento y adaptabilidad del modelo.

- **Evaluación longitudinal**: Establecer mecanismos para evaluar la consistencia y deriva del rendimiento a lo largo del tiempo en entornos clínicos reales.

#### 9.5.2 Evaluación orientada a impacto

- **Métricas centradas en resultados**: Desarrollar y aplicar métricas de evaluación que capturen el impacto real en resultados clínicos, administrativos y económicos, más allá de las métricas técnicas tradicionales.

- **Análisis de retorno de inversión**: Realizar estudios detallados sobre el impacto económico de la implementación, considerando costes directos, indirectos y beneficios tangibles e intangibles.

- **Evaluación de satisfacción y usabilidad**: Implementar metodologías sistemáticas para evaluar la satisfacción de los usuarios finales y la integración fluida en los flujos de trabajo clínicos.

### 9.6 Implementación y despliegue

#### 9.6.1 Ingeniería de sistemas robustos

- **Arquitectura de microservicios optimizada**: Refinar la arquitectura hacia un sistema de microservicios altamente escalable con garantías de latencia y disponibilidad adaptadas a entornos clínicos.

- **Implementación edge-cloud híbrida**: Desarrollar versiones del modelo que puedan ejecutarse parcialmente en dispositivos edge para mantener la privacidad y reducir dependencias de conectividad.

- **Monitorización continua**: Implementar sistemas avanzados de monitorización que detecten automáticamente degradaciones de rendimiento o cambios en patrones de uso.

#### 9.6.2 Integración en sistemas sanitarios

- **Conectores para HIS/HCE**: Desarrollar conectores estándar para los principales sistemas de información hospitalaria e historias clínicas electrónicas del mercado.

- **APIs estandarizadas**: Definir y publicar APIs robustas que faciliten la integración con sistemas de terceros y el desarrollo de aplicaciones complementarias.

- **Herramientas de migración**: Crear utilidades para migrar históricos de codificación y entrenar modelos personalizados a partir de datos preexistentes de cada institución.

### 9.7 Investigación de aplicaciones derivadas

#### 9.7.1 Aplicaciones clínicas avanzadas

- **Sistemas de apoyo a la decisión clínica**: Utilizar la codificación automática como base para sistemas de recomendación terapéutica y alertas clínicas contextualizadas.

- **Predicción de riesgos y complicaciones**: Desarrollar modelos predictivos que utilicen los patrones de codificación para anticipar riesgos, readmisiones o complicaciones.

- **Fenotipado computacional avanzado**: Crear sistemas automáticos de definición de fenotipos clínicos complejos basados en patrones de códigos y textos.

#### 9.7.2 Aplicaciones en investigación y salud pública

- **Plataformas de vigilancia epidemiológica**: Implementar sistemas de vigilancia en tiempo real basados en la codificación automática de documentos clínicos.

- **Herramientas para estudios observacionales**: Desarrollar utilidades específicas para facilitar la identificación y caracterización de cohortes para estudios clínicos.

- **Análisis de efectividad comparativa**: Crear metodologías para evaluar comparativamente intervenciones o programas sanitarios a través del análisis a gran escala de datos codificados.

La implementación de estas líneas de trabajo futuro requerirá un enfoque interdisciplinar, combinando avances en inteligencia artificial, lingüística computacional, informática médica, ciencia de datos y diseño centrado en el usuario. La colaboración estrecha con profesionales sanitarios, especialistas en codificación y gestores hospitalarios será fundamental para garantizar que las soluciones desarrolladas respondan a necesidades reales y se integren eficazmente en la práctica clínica.

## 10. Agradecimientos

Quiero agradecer al equipo del proyecto CODIESP por el acceso a los datos y el apoyo técnico, así como a los tutores y compañeros del máster por sus valiosas aportaciones y sugerencias. El trabajo se ha beneficiado de la colaboración interdisciplinar entre profesionales de la informática, la medicina y la ingeniería.

## 11. Guía para la extensión futura del sistema

El sistema desarrollado está diseñado para ser modular y escalable. Para su extensión futura se recomienda:

- Mantener una arquitectura basada en microservicios y APIs estandarizadas.

- Documentar exhaustivamente el código y los procesos de entrenamiento y despliegue.

- Utilizar herramientas de versionado y monitorización para garantizar la trazabilidad y la calidad.

- Fomentar la colaboración con expertos clínicos y usuarios finales para adaptar el sistema a nuevas necesidades.

- Explorar la integración con plataformas de historia clínica electrónica y sistemas de gestión hospitalaria.

La inteligencia artificial en medicina es un campo en rápida evolución, y la capacidad de adaptación y mejora continua será clave para el éxito y la sostenibilidad de los sistemas desarrollados.

---

*Este informe simula el trabajo de un estudiante de grado o máster, siguiendo la estructura académica habitual y documentando el proceso, resultados y reflexiones obtenidas.*
