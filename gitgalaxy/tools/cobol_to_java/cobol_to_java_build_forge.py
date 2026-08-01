#!/usr/bin/env python3
# ==============================================================================
# GitGalaxy Tool: Java Spring Build System Generator
#
# PURPOSE:
# Auto-generates the Maven pom.xml and application.yml configuration to ensure
# the translated Spring Boot architecture is immediately and perfectly compilable.
#
# ARCHITECTURAL DECISION:
# Generative AI frequently hallucinates incompatible library versions, mixes Maven
# and Gradle paradigms randomly, or omits critical runtime drivers (like PostgreSQL).
# By utilizing this static generation module to lay down the build infrastructure
# and properties, we establish a rigid, compilable sandbox. The autonomous agents
# are then restricted entirely to editing the business logic within the bounds
# of this pre-verified dependency graph.
# ==============================================================================


def generate_pom_xml(group_id: str, artifact_id: str) -> str:
    """Scaffolds a production-ready Maven pom.xml for the microservice."""
    pom = f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.4</version>
        <relativePath/> </parent>

    <groupId>{group_id}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>{artifact_id}</name>
    <description>GitGalaxy Auto-Generated Microservice</description>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-batch</artifactId>
        </dependency>

        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>

        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>

        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
        </dependency>

        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>

        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""
    return pom


def generate_application_yml(artifact_id: str) -> str:
    """Scaffolds the application.yml with standard Postgres and JPA configurations."""
    yml = f"""server:
  port: 8080

spring:
  application:
    name: {artifact_id}

  datasource:
    # TODO: Update these credentials for your target environment
    url: jdbc:postgresql://localhost:5432/{artifact_id.replace("-", "_")}
    username: postgres
    password: password
    driver-class-name: org.postgresql.Driver

  jpa:
    hibernate:
      ddl-auto: update # Automatically creates tables from Entities
    show-sql: true
    properties:
      hibernate:
        format_sql: true
        dialect: org.hibernate.dialect.PostgreSQLDialect

  batch:
    jdbc:
      initialize-schema: always
    job:
      enabled: false # Prevents batch jobs from auto-running on startup
"""
    return yml


def generate_main_class(package_name: str, class_name: str) -> str:
    """Scaffolds the Spring Boot Application entry point."""
    java = f"""package {package_name};

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class {class_name}Application {{

    public static void main(String[] args) {{
        SpringApplication.run({class_name}Application.class, args);
    }}
}}
"""
    return java
